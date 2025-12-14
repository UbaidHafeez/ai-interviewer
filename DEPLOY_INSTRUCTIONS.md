# Deployment Guide for Backend

Since your frontend is on Netlify, you need your backend to be on a public cloud server (not your laptop) so they can talk to each other.

We will use **Render.com** because it has a generous free tier for Python applications.

## Prerequisite: GitHub
1. Ensure your code is pushed to a GitHub repository.
   - If you haven't initialized git yet:
     ```bash
     git init
     git add .
     git commit -m "Initial commit"
     # Create a repo on github.com and follow instructions to push
     ```

## Step 1: Create Render Account
1. Go to [dashboard.render.com](https://dashboard.render.com/).
2. Sign up/Log in (recommend using GitHub login).

## Step 2: Create Web Service
1. Click **"New +"** button and select **"Web Service"**.
2. Select **"Build and deploy from a Git repository"**.
3. Connect your GitHub account if prompted, and select your repository (`Project`).
4. Give it a name (e.g., `my-ai-interviewer-backend`).

## Step 3: Configure Settings
Fill in the following fields:

- **Region**: Closest to you (e.g., Oregon, Frankfurt, Singapore).
- **Branch**: `main` (or `master`).
- **Root Directory**: `.` (leave blank).
- **Runtime**: `Python 3`.
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn backend_server:app`
- **Instance Type**: Select **Free**.

## Step 4: Environment Variables (Critical!)
Scroll down to the "Environment Variables" section and click "Add Environment Variable":

1. **Key**: `GEMINI_API_KEY`
2. **Value**: (Paste your actual API key from your `.env` file here)

*Note: You do not need to add PORT; Render handles that automatically.*

## Step 5: Deploy
1. Click **"Create Web Service"**.
2. Wait for the logs to show "Your service is live".
3. Copy the URL at the top left of the dashboard (e.g., `https://my-ai-interviewer.onrender.com`).

## Step 6: Update Frontend
1. Open your `index.html` file in your local code.
2. Update the `API_BASE` variable:
   ```javascript
   // Replace this:
   // const API_BASE = 'http://127.0.0.1:8000';
   
   // With your new Render URL (no trailing slash):
   const API_BASE = 'https://my-ai-interviewer.onrender.com';
   ```
3. Commit and push your `index.html` change to GitHub. Netlify will detect the change and re-deploy your frontend.

## Important Limitation
**Database Reset**: On the free tier of Render, the disk is "ephemeral". This means every time you deploy or the server restarts (which happens automatically on free tier), your **database.db** will be reset. Your interview history will be lost.
- For a practice app, this is usually fine.
- If you need permanent history, you would need to set up a managed PostgreSQL database (Render provides a free trial for this too), but that requires code changes.
