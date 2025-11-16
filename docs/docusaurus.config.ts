import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
    title: 'Kelvin Documentation',
    tagline: 'The Ultimate Code Examiner',
    favicon: 'img/favicon.svg',

    // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
    future: {
        v4: true, // Improve compatibility with the upcoming Docusaurus v4
    },

    markdown: {
        mermaid: true,
    },
    themes: ['@docusaurus/theme-mermaid'],

    // Set the production url of your site here
    url: 'https://mrlvsb.github.io',
    baseUrl: '/kelvin/',

    // GitHub pages deployment config.
    organizationName: 'mrlvsb',
    projectName: 'kelvin',

    onBrokenLinks: 'throw',

    // Even if you don't use internationalization, you can use this field to set
    // useful metadata like html lang. For example, if your site is Chinese, you
    // may want to replace "en" with "zh-Hans".
    i18n: {
        defaultLocale: 'en',
        locales: ['en'],
    },

    presets: [
        [
            '@docusaurus/preset-classic',
            {
                docs: {
                    sidebarPath: './sidebars.ts',
                    routeBasePath: "/",
                },
                blog: false,
                pages: false,
                theme: {
                    customCss: './src/css/custom.css',
                },
            } satisfies Preset.Options,
        ],
    ],

    themeConfig: {
        image: 'img/docusaurus-social-card.jpg',
        colorMode: {
            respectPrefersColorScheme: true,
        },
        navbar: {
            title: 'Kelvin Docs',
            logo: {
                alt: 'Kelvin Logo',
                src: 'img/logo.svg',
            },
            items: [
                {
                    href: 'https://github.com/mrlvsb/kelvin',
                    label: 'GitHub',
                    position: 'right',
                },
            ],
        },
        docs: {
            sidebar: {
                hideable: false,
                autoCollapseCategories: false
            }
        },
        footer: {
            style: 'dark',
            copyright: `Copyright © ${new Date().getFullYear()} Kelvin, vsb.cz. Built with Docusaurus.`,
        },
        prism: {
            theme: prismThemes.github,
            darkTheme: prismThemes.dracula,
        },
    } satisfies Preset.ThemeConfig,
};

export default config;
