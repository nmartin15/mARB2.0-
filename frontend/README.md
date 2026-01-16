# mARB 2.0 Frontend Dashboard

Optional React-based frontend dashboard for mARB 2.0.

## Features

- Real-time WebSocket notifications
- Risk score visualization
- Claims table with risk indicators
- Statistics dashboard
- Responsive design

## Setup

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Configuration

Create a `.env` file in the `frontend` directory:

```
VITE_API_BASE=http://localhost:8000
VITE_WS_BASE=ws://localhost:8000
```

## Building for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

## Integration with Backend

The frontend connects to the FastAPI backend:
- API endpoints: `/api/v1/*`
- WebSocket: `/ws/notifications`

Make sure the backend is running on `http://localhost:8000` (or update the configuration).

