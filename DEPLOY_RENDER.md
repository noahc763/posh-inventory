# Deploying to Render

## Quick Deploy (Blueprint)
1. Push this folder to a new private Git repo.
2. Go to https://dashboard.render.com, click **New → Blueprint**.
3. Point it at your repo; Render will read `render.yaml`.
4. Click **Apply**. This provisions a free **Web Service** and a free **PostgreSQL** database.
5. Once deployed, open the URL. Register an account, then use **Scan** and **Categories**.

### Notes
- A 1 GB persistent disk is mounted at `uploads/` for your images.
- Database URL is injected from the managed Postgres.
- If you import existing data later, set `DATABASE_URL` to your external DB and redeploy.
