import type { Config } from 'tailwindcss'
import animatePlugin from 'tailwindcss-animate'
import typographyPlugin from '@tailwindcss/typography'

export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  prefix: '',
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1600px',
      },
    },
    extend: {
      fontFamily: {
        sans: ['Golos Text', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        status: {
          success: 'hsl(var(--status-success))',
          warning: 'hsl(var(--status-warning))',
          error: 'hsl(var(--status-error))',
          info: 'hsl(var(--status-info))',
        },
        // Палитра макетов «Пульс бизнеса» v6 — значения из разметки макета.
        ink: {
          DEFAULT: '#121316',
          2: '#45484F',
          3: '#6B6E76',
          4: '#9A9CA2',
        },
        line: {
          DEFAULT: '#E6E7EA',
          strong: '#DADBDF',
          soft: '#EEEFF1',
          ring: '#B8BABF',
          dashed: '#C9CBD0',
        },
        surface: {
          page: '#F2F3F5',
          chip: '#EAEBEE',
          cell: '#F7F7F8',
          drop: '#FAFAFB',
          off: '#D5D7DB',
        },
        brand: {
          DEFAULT: '#EF3124',
          hover: '#D92A1E',
          active: '#C02418',
        },
        // Тоны тегов: подложка и текст одного цветового семейства.
        tone: {
          risk: '#FDE8E6',
          'risk-fg': '#B42318',
          opp: '#E3F5EA',
          'opp-fg': '#137A3D',
          hyp: '#FFF1D6',
          'hyp-fg': '#8A5300',
          info: '#E5EEFF',
          'info-fg': '#2B5BD7',
          ai: '#F1ECFD',
          'ai-fg': '#5B2FC2',
          bank: '#FDEBE9',
          'bank-fg': '#B3261E',
          fact: '#EEEFF1',
          'fact-fg': '#3D4048',
          calc: '#E8F0FA',
          'calc-fg': '#2659A8',
          peach: '#FFE7DC',
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar-background))',
          foreground: 'hsl(var(--sidebar-foreground))',
          primary: 'hsl(var(--sidebar-primary))',
          'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          border: 'hsl(var(--sidebar-border))',
          ring: 'hsl(var(--sidebar-ring))',
        },
      },
      borderRadius: {
        xl: 'calc(var(--radius) + 8px)',
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 4px)',
        sm: 'calc(var(--radius) - 6px)',
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
      },
    },
  },
  plugins: [animatePlugin, typographyPlugin],
} satisfies Config
