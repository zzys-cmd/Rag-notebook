import { defineStore } from 'pinia';

export const useThemeStore = defineStore('theme', {
  state: () => ({
    currentTheme: localStorage.getItem('theme') || 'light',
    themes: {
      light: {
        name: '浅色·温润',
        bg: '#FAF7F2',
        surface: '#F5F0E8',
        card: '#FFFFFF',
        text: '#3D3226',
        textLight: '#6B5F4F',
        textLighter: '#8B7E6F',
        textLightest: '#ADA296',
        primary: '#D4914A',
        tabbarActive: '#D4914A',
        border: '#E5DDD0',
        borderLight: '#F0EBE1',
        divider: '#EDE6DA',
        shadow: 'rgba(139, 126, 111, 0.12)',
      },
      dark: {
        name: '深色·沉静',
        bg: '#1C1916',
        surface: '#2C2722',
        card: '#3C352E',
        text: '#EDE8E0',
        textLight: '#D1C7BC',
        textLighter: '#BDB0A2',
        textLightest: '#A49688',
        primary: '#D4914A',
        tabbarActive: '#8A7044',
        border: '#4A4037',
        borderLight: '#3C342D',
        divider: '#352E28',
        shadow: 'rgba(0, 0, 0, 0.40)',
      },
    },
  }),

  getters: {
    getCurrentTheme: (state) => state.currentTheme,
    getThemeConfig: (state) => state.themes[state.currentTheme],
    getAllThemes: (state) =>
      Object.keys(state.themes).map((key) => ({
        id: key,
        name: state.themes[key].name,
        primaryColor: state.themes[key].primary,
        bgColor: state.themes[key].bg,
      })),
  },

  actions: {
    setTheme(themeName) {
      if (this.themes[themeName]) {
        this.currentTheme = themeName;
        localStorage.setItem('theme', themeName);
        this.applyTheme();
      }
    },

    applyTheme() {
      const t = this.themes[this.currentTheme];
      const root = document.documentElement;
      root.style.setProperty('--color-bg', t.bg);
      root.style.setProperty('--color-surface', t.surface);
      root.style.setProperty('--color-card', t.card);
      root.style.setProperty('--color-text', t.text);
      root.style.setProperty('--color-text-light', t.textLight);
      root.style.setProperty('--color-text-lighter', t.textLighter);
      root.style.setProperty('--color-text-lightest', t.textLightest);
      root.style.setProperty('--color-primary', t.primary);
      root.style.setProperty('--color-border', t.border);
      root.style.setProperty('--color-border-light', t.borderLight);
      root.style.setProperty('--color-divider', t.divider);
      root.style.setProperty('--van-tabbar-item-active-color', t.tabbarActive);
      root.style.setProperty('--color-shadow', t.shadow);
    },

    initTheme() {
      this.applyTheme();
    },
  },
});