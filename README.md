# LakBayad - Trip Expense Splitter

A modern expense splitting app for group trips, built with Python and Flet.

## Features

- 🎫 Create and join trips with invite codes
- 👥 Add participants and manage trip members
- 💰 Track expenses with selective splitting
- 📊 Smart settlement calculations (optimized for fewest transactions)
- 🔄 Offline mode - add expenses without internet
- ✏️ Trip creator powers: edit nicknames, remove participants
- 📱 Works on web, desktop, and mobile

## Local Development

### Prerequisites
- Python 3.10+
- Supabase account

### Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Update `config.py` with your Supabase credentials

3. Run:
```bash
python main.py
```

## Deployment to Render.com

### Configuration:
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python main.py`
- **Instance Type:** Free

### Environment Variables:
```
SUPABASE_URL = your_project_url
SUPABASE_ANON_KEY = your_anon_key
```

Your app will be live at: `https://lakbayad.onrender.com`

## License
Private project