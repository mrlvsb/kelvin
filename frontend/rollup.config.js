import commonjs from '@rollup/plugin-commonjs';
import resolve from '@rollup/plugin-node-resolve';
import replace from '@rollup/plugin-replace';
import terser from '@rollup/plugin-terser';
import autoprefixer from 'autoprefixer';
import livereload from 'rollup-plugin-livereload';
import postcss from 'rollup-plugin-postcss';
import svelte from 'rollup-plugin-svelte';
import typescript from 'rollup-plugin-typescript2';
import vue from 'rollup-plugin-vue';
import sass from 'sass';

const production = !process.env.ROLLUP_WATCH;

function serve() {
	let server;
	
	function toExit() {
		if (server) server.kill(0);
	}

	return {
		writeBundle() {
			if (server) return;
			server = require('child_process').spawn('npm', ['run', 'start', '--', '--dev'], {
				stdio: ['ignore', 'inherit', 'inherit'],
				shell: true
			});

			process.on('SIGTERM', toExit);
			process.on('exit', toExit);
		}
	};
}

export default {
	input: 'src/main.js',
	output: {
		sourcemap: true,
		format: 'iife',
		name: 'app',
		file: '../web/static/frontend.js'
	},
	plugins: [
		svelte({
            emitCss: true,
		}),

		vue({
            preprocessStyles: true,
        }),
        // Replace the environment variables - https://github.com/rollup/rollup/issues/805
        // btw the vue/dist/vue.esm.browser didn't work
        replace({
            'process.env.NODE_ENV': JSON.stringify('development'),
            'process.env.VUE_ENV': JSON.stringify('browser'),
        }),
        typescript({
            abortOnError: production,
        }),

		// If you have external dependencies installed from
		// npm, you'll most likely need these plugins. In
		// some cases you'll need additional configuration -
		// consult the documentation for details:
		// https://github.com/rollup/plugins/tree/master/packages/commonjs
		resolve({
			browser: true,
			dedupe: ['svelte']
		}),
		commonjs(),

        postcss({
            preprocessor: (content, id) => {
                return sass.compile(id).toString();
            },
            extract: true,
            minimize: production,
            sourceMap: production,
            plugins: [
                autoprefixer,
            ]
        }),

		// In dev mode, call `npm run start` once
		// the bundle has been generated
		!production && serve(),

		// Watch the `public` directory and refresh the
		// browser on changes when not in production
		!production && livereload('public'),

		// If we're building for production (npm run build
		// instead of npm run dev), minify
		production && terser()
	],
	watch: {
		clearScreen: false
	}
};
