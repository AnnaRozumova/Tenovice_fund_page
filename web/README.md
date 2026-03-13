# Tenovice Fundraising Frontend

Simple, static landing page for the Tenovice fundraising campaign.

## Quick Start

Just open `index.html` in your browser! No installation needed.

## Configuration

Edit `config.js` to update:

```javascript
const CONFIG = {
  // Your API URL
  API_URL: 'https://your-api-id.execute-api.region.amazonaws.com',

  // Hardcoded values
  CURRENT_BALANCE: 12500,  // Update this manually
  FUNDRAISING_GOAL: 50000, // Update this manually
};
```

## Customization

### Add Logo
1. Place your logo file (e.g., `logo.png`) in the `web/` folder
2. Edit `index.html`, replace:
   ```html
   <div class="logo-placeholder">LOGO</div>
   ```
   with:
   ```html
   <img src="logo.png" alt="Tenovice Logo" style="max-height: 80px;">
   ```

### Add Images
1. Place images in `web/images/` folder
2. Edit `index.html`, replace image placeholders:
   ```html
   <div class="image-placeholder">Image 1</div>
   ```
   with:
   ```html
   <img src="images/your-image.jpg" alt="Description">
   ```

### Edit Text
Simply edit the HTML in `index.html`:
- Title: `<h1 class="title">`
- Description: `<p class="description">`

## Deploy to S3

### Option 1: AWS CLI
```bash
# Configure AWS CLI first
aws configure

# Sync to S3 bucket
aws s3 sync . s3://your-bucket-name --exclude ".git/*" --exclude "README.md"

# Make bucket public for website hosting
aws s3 website s3://your-bucket-name --index-document index.html
```

### Option 2: AWS Console
1. Open S3 console
2. Create/select your bucket
3. Upload all files: `index.html`, `style.css`, `config.js`, `main.js`, and any images
4. Go to bucket Properties → Static website hosting → Enable
5. Set index document: `index.html`
6. Go to Permissions → Edit bucket policy (make public)

### Example Bucket Policy for Public Access
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    }
  ]
}
```

## Files

```
web/
├── index.html      # Main page
├── style.css       # Styling
├── config.js       # Configuration (API URL, hardcoded values)
├── main.js         # JavaScript logic
└── README.md       # This file
```

## Features

- ✅ No build tools needed
- ✅ Works directly in browser
- ✅ Fully responsive design
- ✅ Live pledge statistics from API
- ✅ Animated progress bar
- ✅ Ready for S3 static hosting

## Testing Locally

You can test by simply opening `index.html` in a browser, but API calls may be blocked by CORS if testing from `file://` protocol.

To test properly:

**Option 1: Python**
```bash
cd web
python -m http.server 8000
# Open http://localhost:8000
```

**Option 2: PHP**
```bash
cd web
php -S localhost:8000
# Open http://localhost:8000
```

**Option 3: VS Code Live Server Extension**
- Install "Live Server" extension
- Right-click `index.html` → Open with Live Server
