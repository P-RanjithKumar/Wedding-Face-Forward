# Wedding Face Forward - Frontend

A beautiful, modern web interface for guests to find their photos using AI face recognition.

## ✨ Features

- 📱 **Mobile-First Design** - Beautiful on any device
- 🎨 **Modern Aesthetic** - Glassmorphism, smooth animations, dark theme
- 📷 **Easy Selfie Upload** - Drag & drop or camera capture
- 🧠 **Instant AI Matching** - Find your photos in seconds
- 🖼️ **Gallery View** - Browse Solo & Group photos
- 💾 **Download Ready** - Save your favorite moments

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ (for frontend development)
- Python 3.10+ (for API server)
- Backend worker running (see `../backend/README.md`)

### 1. Install Dependencies

```powershell
# Frontend (for development with hot reload)
cd "c:\Users\ranji\Desktop\MYwork\Wedding Face Forward\frontend"
npm install

# API Server
pip install -r requirements.txt
```

### 2. Start the Development Servers

**Option A: Both servers together (recommended)**

```powershell
# Terminal 1: Start the API server (port 8000)
cd "c:\Users\ranji\Desktop\MYwork\Wedding Face Forward\frontend"
python server.py

# Terminal 2: Start the frontend dev server (port 3000)
cd "c:\Users\ranji\Desktop\MYwork\Wedding Face Forward\frontend"
npm run dev
```

**Option B: API server only (serves static files)**

```powershell
# Build the frontend first
npm run build

# Start the server (serves both API and static files)
python server.py
```

### 3. Open in Browser

- Development: http://localhost:3000
- Production: http://localhost:8000

## 📁 Project Structure

```
frontend/
├── index.html          # Main HTML page
├── css/
│   └── main.css        # Complete design system
├── js/
│   └── main.js         # Application logic
├── server.py           # FastAPI backend server
├── requirements.txt    # Python dependencies
├── package.json        # Node.js config
└── vite.config.js      # Vite build config
```

## 🎨 Design System

### Colors

- **Primary**: Rose Gold gradient (`#ec4899` → `#8b5cf6`)
- **Background**: Deep purple-black (`#0f0a14`)
- **Accents**: Violet highlights with glow effects

### Typography

- **Display**: Playfair Display (elegant serif)
- **Body**: Inter (clean sans-serif)

### Effects

- Glassmorphism with backdrop blur
- Smooth spring animations
- Floating particle shapes
- Gradient glow shadows

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/stats` | Processing statistics |
| POST | `/api/enroll` | Submit selfie for matching |
| GET | `/api/photos/{name}` | Get user's photos |
| GET | `/api/photo?path=` | Serve full photo |
| GET | `/api/thumbnail?path=` | Serve thumbnail |
| GET | `/api/persons` | List all person clusters |

## 📱 User Flow

1. **Landing** - Guest sees hero section with event stats
2. **Enroll** - Upload selfie, enter name & contact info
3. **Match** - AI finds their face cluster
4. **Result** - See photo count and preview
5. **Gallery** - Browse all Solo & Group photos
6. **Download** - Save favorite photos

## 🔧 Configuration

The frontend server uses the same configuration as the backend:

- `EVENT_ROOT` - Base folder for photos
- `DB_PATH` - SQLite database location
- `CLUSTER_THRESHOLD` - Face matching sensitivity

## 🐛 Troubleshooting

### "No match found"

- Photos may still be processing
- Try a clearer, well-lit selfie
- Face should be clearly visible and facing camera

### Server won't start

- Ensure backend dependencies are installed
- Check that the backend `.env` file exists
- Verify Python path includes backend folder

### Photos not loading

- Check that the photo processing worker is running
- Verify folder permissions on EventRoot

## 📄 License

MIT
