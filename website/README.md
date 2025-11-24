# Surf Tracker Website

Next.js 14 frontend for Surf Tracker application.

## Getting Started

### Development (with Docker)

```bash
docker compose up website
```

### Development (local)

```bash
cd website
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **UI Library**: shadcn/ui (Radix UI + Tailwind CSS)
- **Forms**: React Hook Form + Zod
- **Styling**: Tailwind CSS
- **API Client**: Axios

## Project Structure

```
src/
├── app/              # Next.js app directory
│   ├── layout.tsx    # Root layout
│   ├── page.tsx      # Home page
│   └── ...
├── components/       # React components
│   ├── ui/           # shadcn/ui components
│   └── ...
├── lib/              # Utilities
│   ├── api-client.ts # API client
│   └── utils.ts      # Helper functions
└── hooks/            # Custom React hooks
```

## TODO

- [ ] Implement authentication pages (register, login)
- [ ] Build dashboard with session list
- [ ] Create video upload component
- [ ] Implement session results viewer
- [ ] Add profile management
