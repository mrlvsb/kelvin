import { svelte } from '@sveltejs/vite-plugin-svelte';
import vue from '@vitejs/plugin-vue';
import autoprefixer from 'autoprefixer';
import { defineConfig } from 'vite';

export default defineConfig((env) => {
    const production = env.mode === 'production';

    return {
        define: {
            'process.env.NODE_ENV': production ? '"production"' : '"development"',
            'process.env.VUE_ENV': '"browser"',
            __VUE_PROD_DEVTOOLS__: false
        },
        plugins: [
            vue(),
            svelte({
                emitCss: true
            })
        ],
        build: {
            lib: {
                entry: 'src/main.js',
                fileName: () => 'frontend.js',
                formats: ['iife'],
                name: 'main.js'
            },
            sourcemap: true,
            outDir: '../web/static',
            minify: production ? 'terser' : undefined,
            rollupOptions: {
                output: {
                    assetFileNames: 'frontend.[ext]'
                }
            }
        },
        css: {
            postcss: {
                plugins: [autoprefixer()]
            }
        }
    };
});
