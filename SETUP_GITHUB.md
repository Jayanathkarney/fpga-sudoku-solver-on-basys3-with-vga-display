# How to Create and Push This Repo to GitHub
## (Step-by-step guide — beginner friendly)

---

## STEP 1 — Install Git on Your PC (if not already)

**Check if Git is installed:**
```bash
git --version
```
If you see a version number, you're good. If not:
- **Windows**: Download from https://git-scm.com/download/win and install
- **Linux**: `sudo apt install git`
- **Mac**: `xcode-select --install`

---

## STEP 2 — Configure Git with Your Identity (one-time setup)

Open a terminal (or Git Bash on Windows) and run:
```bash
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
```
Use the same email as your GitHub account.

---

## STEP 3 — Create the Repo on GitHub

1. Go to https://github.com and log in
2. Click the **"+"** icon (top-right) → **"New repository"**
3. Fill in:
   - **Repository name**: `fpga-sudoku-solver`
   - **Description**: `Hardware Sudoku solver on Basys3 FPGA using AC-3 + MRV backtracking, with VGA display`
   - **Visibility**: ✅ Public
   - ❌ Do NOT check "Add a README file" (we already have one)
   - ❌ Do NOT add .gitignore or license here (we already have them)
4. Click **"Create repository"**

GitHub will show you an empty repo page. Keep this tab open.

---

## STEP 4 — Set Up the Folder on Your PC

Create a folder called `fpga-sudoku-solver` on your PC. Inside it, create these subfolders:

```
fpga-sudoku-solver/
├── rtl/                 ← put all your .v files here
├── constraints/         ← put your .xdc file here
├── python_host/         ← put your Python script here
├── vivado/              ← put your Vivado project files here
├── docs/                ← put your PDF report here
├── README.md            ← copy the README from this repo
└── .gitignore           ← copy the .gitignore from this repo
```

> **Tip**: The README.md and .gitignore files are provided in this repository — just copy them into your folder.

---

## STEP 5 — Initialize Git in Your Folder

Open a terminal and navigate to your project folder:
```bash
cd path/to/fpga-sudoku-solver
```
For example on Windows:
```bash
cd C:\Users\YourName\Documents\fpga-sudoku-solver
```

Now initialize Git:
```bash
git init
```
You'll see: `Initialized empty Git repository in .../fpga-sudoku-solver/.git/`

---

## STEP 6 — Add All Your Files

```bash
git add .
```
This stages all files (tells Git "track these"). The `.gitignore` will automatically skip Vivado cache/log files.

Check what's been staged:
```bash
git status
```
You'll see a list of files in green — these are ready to be committed.

---

## STEP 7 — Make Your First Commit

```bash
git commit -m "Initial commit: FPGA Sudoku Solver — AC-3, MRV backtracking, VGA display"
```
A **commit** is like saving a snapshot of your project at this point in time.

---

## STEP 8 — Link Your Local Folder to GitHub

Go back to your GitHub repo page. You'll see a section like:
> **…or push an existing repository from the command line**

Copy the commands shown there. They will look like:
```bash
git remote add origin https://github.com/YOUR-USERNAME/fpga-sudoku-solver.git
git branch -M main
git push -u origin main
```

Run these in your terminal. Git will ask for your GitHub username and password.

> **Note on password**: GitHub no longer accepts your account password here. You need a **Personal Access Token** instead. See below.

---

## STEP 8a — Create a GitHub Personal Access Token (if asked for password)

1. Go to GitHub → Click your profile picture (top-right) → **Settings**
2. Scroll down → **Developer settings** (bottom of left sidebar)
3. **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**
4. Give it a name (e.g., `my-laptop`), set expiry, and check **`repo`** scope
5. Click **Generate token** — copy it immediately (you won't see it again)
6. Use this token as your password when Git prompts you

---

## STEP 9 — Verify It Worked

Refresh your GitHub repo page. You should now see all your files listed there!

---

## STEP 10 — Future Updates (How to push new changes)

Whenever you modify files and want to save them to GitHub:
```bash
git add .
git commit -m "Brief description of what you changed"
git push
```
That's it. Three commands every time.

---

## Quick Reference — Git Commands You'll Use

| Command | What it does |
|---------|-------------|
| `git init` | Start tracking a folder with Git |
| `git add .` | Stage all changed files |
| `git status` | See what's changed / staged |
| `git commit -m "message"` | Save a snapshot with a description |
| `git push` | Upload commits to GitHub |
| `git pull` | Download latest changes from GitHub |
| `git log` | See history of all commits |

---

## Recommended Repo Description for GitHub

When creating the repo, use this as the description:
> Hardware Sudoku solver on Digilent Basys3 (Artix-7 FPGA) — parallel AC-3 constraint propagation + MRV-guided backtracking in Verilog, with VGA display and UART interface. IISc E3-231 course project.

And add these **topics** on GitHub (click the gear icon next to "About"):
`fpga` `verilog` `sudoku` `basys3` `artix-7` `vga` `uart` `constraint-satisfaction` `digital-design` `iisc`
