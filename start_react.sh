#!/bin/bash
# Start BoltSizer React frontend and FastAPI backend

echo "Starting BoltSizer FastAPI backend on port 8000..."
cd "$(dirname "$0")"
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

echo "Starting BoltSizer React frontend on port 5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "BoltSizer is running:"
echo "  React app:  http://localhost:5173"
echo "  API docs:   http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $API_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
