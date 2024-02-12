import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
//import { viteSingleFile } from "vite-plugin-singlefile"
import { resolve } from "path"

// https://vitejs.dev/config/



export default defineConfig({
    alias: {
        "@": resolve(__dirname, "./src")
    },
    plugins: [vue()],
    build: {
        outDir: "../web/static/vuets",
        emptyOutDir: true,
        watch: {
            // https://rollupjs.org/configuration-options/#watch
        },

        rollupOptions: {
            input: {
                vuets: 'index.html',
            },
            output: {
                entryFileNames: '[name].js',
                // FROM: https://stackoverflow.com/questions/68992086/how-can-i-assign-a-custom-css-file-name-when-building-a-vite-application
                assetFileNames: (assetInfo) => {
                    if (assetInfo.name == 'style.css')
                        return 'customname.css';
                    return assetInfo.name;
                },
            },
        },
    },
    server: {
        proxy: {
            '^/api/*': {
                target: 'http://localhost:8000/',
                secure: false,
                changeOrigin: true,
                ws: true,
                configure: (proxy, _options) => {
                    proxy.on('error', (err, _req, _res) => {
                        console.log('proxy error', err);
                    });
                    proxy.on('proxyReq', (proxyReq, req, _res) => {
                        console.log('Sending Request to the Target:', req.method, req.url);
                    });
                    proxy.on('proxyRes', (proxyRes, req, _res) => {
                        console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
                    });
                },
            }
        }
    }
})
