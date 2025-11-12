# Time Card Sign-Off Frontend

This is the Next.js frontend application for the Time Card Sign-Off system. It provides a modern, responsive UI built with React, TypeScript, and Tailwind CSS.

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- The FastAPI backend running (see main project README)

### Installation

1. Install dependencies:
```bash
npm install
```

2. Create a `.env.local` file in the `frontend` directory:
```bash
cd frontend
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
```

### Development

1. Make sure the FastAPI backend is running (see main project README)

2. Run the development server from the `frontend` directory:
```bash
cd frontend
npm run dev
```

3. Open [http://localhost:3000](http://localhost:3000) in your browser.

4. To test the signup form, you'll need a valid magic link token. The signup URL format is:
   ```
   http://localhost:3000/signup?token=YOUR_TOKEN_HERE
   ```

### Building for Production

```bash
npm run build
npm start
```

## Project Structure

- `app/` - Next.js App Router pages and layouts
  - `signup/` - Signup page with form
- `lib/` - Utility functions and API client
  - `api.ts` - API client for communicating with FastAPI backend

## Features

- **Modern UI**: Built with Tailwind CSS for a beautiful, responsive design
- **Type Safety**: Full TypeScript support
- **Form Validation**: Client-side validation with error handling
- **API Integration**: Seamless communication with FastAPI backend

## Environment Variables

- `NEXT_PUBLIC_API_URL` - The URL of the FastAPI backend (default: `http://localhost:8000`)

## API Endpoints Used

- `GET /api/validate-magic-link?token=...` - Validates a magic link token
- `POST /submit-signup` - Submits the signup form
