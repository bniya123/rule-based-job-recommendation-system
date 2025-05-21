import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import PCA
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity
from geopy.distance import geodesic
from geopy.geocoders import OpenCage
from geopy.extra.rate_limiter import RateLimiter
import functools
from pathlib import Path

# Cache file for storing geocoded locations
CACHE_FILE = Path("location_cache.csv")
GEOCODE_API_KEY = "e16212d2c51a4da288bf22c3dced407d"

def recommend_unsupervised(
    skills: str,
    location: str,
    expected_monthly_salary: float,
    jobs_csv_path: str = "jobs.csv",
    top_n: int = 5
) -> pd.DataFrame:
    """
    Recommend jobs based on skills, location, and expected salary.
    
    Args:
        skills: Comma-separated string of skills/job types (e.g. "Data Analyst, Python").
        location: User's location (state or city).
        expected_monthly_salary: User's expected monthly salary in INR.
        jobs_csv_path: Path to jobs CSV file.
        top_n: Number of recommendations to return.
        
    Returns:
        DataFrame of top N recommended jobs with similarity, distance, salary, and explanations.
    """
    # Load jobs
    jobs = pd.read_csv(jobs_csv_path)

    # Preprocessing
    jobs['Job type'] = jobs['Job type'].fillna('').astype(str)
    jobs['job_description'] = jobs['job_description'].fillna('').astype(str)
    jobs['job_text'] = (jobs['Job type'] + " " + jobs['job_description']).astype(str)

    # Convert salary columns to numeric
    jobs['Min salary'] = pd.to_numeric(jobs.get('Min salary', 0), errors='coerce').fillna(0)
    jobs['Max salary'] = pd.to_numeric(jobs.get('Max salary', 0), errors='coerce').fillna(0)

    # Geolocation setup
    geolocator = OpenCage(api_key=GEOCODE_API_KEY)
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    def load_cache() -> dict:
        if CACHE_FILE.exists():
            df = pd.read_csv(CACHE_FILE)
            return dict(zip(df['location'], zip(df['lat'], df['lon'])))
        return {}

    location_cache = load_cache()

    @functools.lru_cache(maxsize=512)
    def get_coordinates(name: str):
        if pd.isna(name) or not name:
            return None
        if name in location_cache:
            return location_cache[name]
        try:
            loc = geocode(name)
            if loc:
                coords = (loc.latitude, loc.longitude)
                location_cache[name] = coords
                pd.DataFrame([{'location': name, 'lat': coords[0], 'lon': coords[1]}]).to_csv(
                    CACHE_FILE, mode='a', header=not CACHE_FILE.exists(), index=False
                )
                return coords
        except:
            return None

    # Add coordinates to jobs if not already present
    if 'coords' not in jobs.columns:
        jobs['coords'] = jobs['State'].apply(get_coordinates)

    # Sentence Transformer embedding
    model_name = 'all-MiniLM-L6-v2'
    bert = SentenceTransformer(model_name)
    job_embeddings = bert.encode(jobs['job_text'].tolist(), show_progress_bar=False)

    # PCA for dimensionality reduction (optional but speeds similarity)
    pca = PCA(n_components=50)
    job_pca = pca.fit_transform(job_embeddings)

    # Embed user skills profile
    profile_emb = bert.encode([skills])
    profile_pca = pca.transform(profile_emb)

    # Cosine similarity between user profile and job embeddings
    similarities = cosine_similarity(profile_pca, job_pca).flatten()

    # Filter jobs by salary range
    salary_mask = (jobs['Min salary'] <= expected_monthly_salary) & (jobs['Max salary'] >= expected_monthly_salary)
    filtered_jobs = jobs[salary_mask].copy()
    filtered_similarities = similarities[salary_mask.values]

    # Compute distance from user location to job location
    user_coords = get_coordinates(location)

    def distance_to_user(row):
        if pd.isna(row['coords']) or user_coords is None:
            return np.inf
        try:
            return geodesic(row['coords'], user_coords).km
        except:
            return np.inf

    filtered_jobs['Distance_km'] = filtered_jobs.apply(distance_to_user, axis=1)

    # Normalize similarity and distance
    sim_vals = filtered_similarities.reshape(-1, 1)
    dist_vals = filtered_jobs['Distance_km'].values.reshape(-1, 1)

    norm_sim = MinMaxScaler().fit_transform(sim_vals) if len(set(sim_vals.flatten())) > 1 else np.ones_like(sim_vals)
    norm_dist = MinMaxScaler().fit_transform(dist_vals) if len(set(dist_vals.flatten())) > 1 else np.zeros_like(dist_vals)

    # Final score weights: prioritize similarity and penalize distance
    final_scores = (0.7 * norm_sim) - (0.3 * norm_dist)

    filtered_jobs = filtered_jobs.reset_index()
    filtered_jobs['Similarity'] = filtered_similarities
    filtered_jobs['Norm_Similarity'] = norm_sim.flatten()
    filtered_jobs['Norm_Distance'] = norm_dist.flatten()
    filtered_jobs['Final_Score'] = final_scores.flatten()

    # Sort by final score descending
    recommended = filtered_jobs.sort_values('Final_Score', ascending=False).head(top_n).copy()

    # Add explanatory column
    recommended['Expected Salary Range'] = recommended['Min salary'].astype(int).astype(str) + " - " + recommended['Max salary'].astype(int).astype(str)
    recommended['Explanation'] = recommended.apply(
        lambda r: f"Similarity: {r.Similarity:.2f}, Distance: {r.Distance_km:.1f} km, Score: {r.Final_Score:.2f}, Salary: {r['Min salary']}-{r['Max salary']} INR",
        axis=1
    )

    # Select relevant columns for output
    return recommended[[
        'Company', 'Job type', 'State', 'job_description',
        'Expected Salary Range', 'Distance_km', 'Final_Score', 'Explanation'
    ]].rename(columns={'Distance_km': 'Distance (km)', 'Final_Score': 'Match Score'})
