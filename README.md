# cryptic_crossword_helper

A web-based cryptic crossword game that generates interactive puzzles from The Times crossword JSON feeds.

## Features

- Interactive crossword grid with typing support
- Clue list with reveal functionality
- Local storage for game state persistence
- Automatic generation from weekly crossword data
- GitHub Pages deployment

## Setup

1. Clone the repository
2. Run the generation script with a crossword JSON URL:
   ```bash
   curl -s <crossword_url> > crossword.json
   python scripts/extract_answers.py crossword.json > game_data.json
   python scripts/generate_html.py src/template.html game_data.json index.html
   ```

## GitHub Actions

The repository includes a GitHub Action workflow that can be triggered manually to generate and deploy a new crossword game:

1. Go to Actions tab
2. Select "Generate Crossword Game" workflow
3. Click "Run workflow"
4. Enter the crossword JSON URL
5. The game will be deployed to GitHub Pages

## Local Development

To test locally:
```bash
python -m http.server 8000
```
Then open http://localhost:8000 in your browser.

## Project Structure

- `scripts/extract_answers.py` - Extracts answers from crossword JSON
- `scripts/generate_html.py` - Generates HTML from template and data
- `src/template.html` - HTML template for the game
- `.github/workflows/generate.yml` - GitHub Action for automated generation
