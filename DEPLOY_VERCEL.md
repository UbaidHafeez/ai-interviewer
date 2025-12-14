# Deploying to Vercel (Free Backend)

Since Render was asking for credit card verification, we have converted your backend to be "Stateless" so it can run on **Vercel** for free without a database.

## Prerequisites
1.  **Push your latest code to GitHub** (We already did this in the chat).
    - If you are unsure, run `git add .`, `git commit -m "Update for Vercel"`, `git push origin main`.

## Step 1: Create Vercel Account
1.  Go to [vercel.com](https://vercel.com).
2.  Sign up with **GitHub**.

## Step 2: Import Project
1.  On your Vercel Dashboard, click **"Add New..."** -> **"Project"**.
2.  Select your `ai-interviewer` repository.
3.  Click **Import**.

## Step 3: Configure Project
1.  **Framework Preset**: Select **Other**.
2.  **Environment Variables**:
    - Click to expand.
    - Add: `GEMINI_API_KEY`
    - Value: (Copy from your `.env.local`)
3.  Click **Deploy**.

## Step 4: Get Your Backend URL
1.  Once deployed (confetti!), you will see a URL domain (e.g., `ai-interviewer-beta.vercel.app`).
2.  **Copy this URL**.

## Step 5: Update Frontend (Index.html)
1.  Open `d:\WORK\Project\index.html` on your computer.
2.  Find this line (around line 485):
    ```javascript
    const API_BASE = 'https://YOUR-VERCEL-PROJECT.vercel.app';
    ```
3.  Replace the placeholder with your **actual Vercel URL** (e.g., `https://ai-interviewer-beta.vercel.app`).
4.  Save the file.

## Step 6: Push Frontend Changes
1.  Run these commands to update your GitHub (which updates Netlify):
    ```powershell
    git add index.html
    git commit -m "Link frontend to Vercel backend"
    git push origin main
    ```

**Done!** Your Netlify site will now talk to your Vercel backend.
