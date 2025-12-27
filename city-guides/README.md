City Microguides — Budget Picks

Quick prototype: local JSON dataset with searchable city venues by budget.

Run:

1. Activate your venv (or use system Python).

   In PowerShell:

   & 'C:\\Users\\markm\\OneDrive\\Desktop\\Mturk\\venv\\Scripts\\Activate.ps1'

2. Install requirements:

   pip install -r requirements.txt

3. Run app:

   python app.py

Open http://127.0.0.1:5010

## Testing on iPhone 📱

To test the app on your iPhone:

1. Make sure your iPhone is on the **same WiFi network** as your computer
2. Run the helper script from the root directory to get your network IP:
   ```
   python ../get_network_ip.py
   ```
3. Open Safari on your iPhone and navigate to the URL shown (e.g., http://192.168.1.x:5010)
4. The app should work fully on your iPhone

Data: `data/venues.json` contains curated sample venues. Edit or expand as needed.