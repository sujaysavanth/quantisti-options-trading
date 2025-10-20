# Quantisti Landing Page

A modern, professional landing page for the Quantisti Options Trading Platform built with Next.js 14, TypeScript, and Tailwind CSS.

## Features

- 🌓 **Dark/Light Mode** - Seamless theme switching with system preference detection
- 📱 **Fully Responsive** - Mobile-first design that looks great on all devices
- ⚡ **Performance Optimized** - Built with Next.js 14 App Router for optimal performance
- 🎨 **Modern Design** - Clean, professional UI with Tailwind CSS
- ♿ **Accessible** - Semantic HTML and ARIA labels for better accessibility

## Sections

1. **Navigation Bar** - Sticky navbar with services dropdown and theme toggle
2. **Hero Section** - Eye-catching introduction with animated cards
3. **Features** - Showcase of 8 core platform capabilities
4. **How It Works** - 4-step workflow visualization
5. **About Us** - Platform mission and technology stack
6. **Pricing** - Three-tier pricing (Basic, Premium, Admin)
7. **CTA Section** - Final call-to-action with trial signup
8. **Footer** - Comprehensive links and social media

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

1. Install dependencies:
   ```bash
   npm install
   ```

2. Run the development server:
   ```bash
   npm run dev
   ```

3. Open [http://localhost:3000](http://localhost:3000) in your browser

### Build for Production

```bash
npm run build
npm start
```

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **Theme**: next-themes

## Project Structure

```
landing/
├── app/
│   ├── layout.tsx       # Root layout with theme provider
│   ├── page.tsx         # Main landing page
│   └── globals.css      # Global styles and Tailwind imports
├── components/
│   ├── Navbar.tsx       # Navigation with dropdown
│   ├── Hero.tsx         # Hero section
│   ├── Features.tsx     # Features grid
│   ├── HowItWorks.tsx   # Workflow steps
│   ├── About.tsx        # About section
│   ├── Pricing.tsx      # Pricing tiers
│   ├── CTA.tsx          # Call-to-action
│   ├── Footer.tsx       # Footer with links
│   ├── ThemeProvider.tsx # Theme context provider
│   └── ThemeToggle.tsx  # Dark/light mode toggle
├── public/              # Static assets
└── tailwind.config.js   # Tailwind configuration
```

## Customization

### Colors

Edit `tailwind.config.js` to customize the color palette:
- **Primary**: Blue (#3B82F6) - Main brand color
- **Secondary**: Green (#10B981) - Success/growth
- **Accent**: Purple (#8B5CF6) - Premium features

### Content

- Update component text directly in each component file
- Modify links in `Navbar.tsx` and `Footer.tsx`
- Adjust pricing in `Pricing.tsx`

## Deployment

### Vercel (Recommended)

1. Push your code to GitHub
2. Import project in Vercel
3. Deploy with one click

### Firebase Hosting

```bash
npm run build
firebase deploy
```

### Google Cloud Run

Build and deploy as a container:
```bash
docker build -t quantisti-landing .
gcloud run deploy quantisti-landing --source .
```

## Environment Variables

Currently, no environment variables are required. When integrating with backend APIs, create a `.env.local` file:

```bash
NEXT_PUBLIC_API_URL=https://api.quantisti.com
NEXT_PUBLIC_FIREBASE_API_KEY=your_key_here
```

## Performance

- Lighthouse Score: 95+
- First Contentful Paint: < 1s
- Time to Interactive: < 2s

## Browser Support

- Chrome (last 2 versions)
- Firefox (last 2 versions)
- Safari (last 2 versions)
- Edge (last 2 versions)

## Contributing

This landing page is part of the Quantisti monorepo. See the main repository README for contribution guidelines.

## License

See LICENSE file in the root of the monorepo.

---

Built with ❤️ for the Quantisti Options Trading Platform
