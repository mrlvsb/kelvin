<script>
import {csrfToken} from './api.js'
import uppie from 'uppie'

let dropping = false;
let dragLeaveTimer = null;
let progress = null;
let error = false;

uppie()(window, {name: 'solution'}, async (event, formData, files) => {
	progress = 0;
	const xhr = new XMLHttpRequest();
	xhr.upload.addEventListener("progress", e => {
		if (e.lengthComputable) {
			progress = Math.round(e.loaded * 100 / e.total);
		}
	}, false);
	xhr.addEventListener('loadend', () => {
		if(xhr.status == 200 && xhr.responseURL) {
			document.location.href = xhr.responseURL + '#result';
		} else {
			error = true;
		}		
	});
	xhr.open('POST', document.location.href);
	xhr.setRequestHeader('X-CSRFToken', csrfToken())
	xhr.send(formData);
});	

function dragstop() {
	if(dragLeaveTimer) {
		clearInterval(dragLeaveTimer);
	}
	dragLeaveTimer = setTimeout(() => dropping = false, 300);
}

function dragstart(e) {
	if(dragLeaveTimer) {
		clearInterval(dragLeaveTimer);
	}

	function hasFiles() {
		if (e.dataTransfer.types) {
			for(const t of e.dataTransfer.types) {
				if(t == 'Files') {
					return true;
				}
			}
		}
		return false;
	}	

	if(hasFiles() && !dropping) {
		dropping = true;
	}
}

function dismiss() {
	if(!error) {
		return;
	}

	error = false;
	dropping = false;
	progress = null;
}

</script>

<svelte:window
	on:dragleave={dragstop}
	on:drop={dragstop}
	on:dragenter={dragstart}
	on:dragover={dragstart}
	/>

<style>
	.dropzone {
		position: fixed;
		top: 0;
		left: 0;
		width: 100vw;
		height: 100vh;
		transition: background-color 100ms;
		visibility: hidden;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 10rem;
		text-align: center;
	}

	.dropzone.uploading:not(.dropzone.error) {
		cursor: wait;
	}

	.dropzone.dropping, .dropzone.uploading {
		visibility: visible;
		background: #007bff50;
	}

	.dropzone.error {
		background: #f5c6cbcc;
		font-size: 3rem;
	}
</style>

<div class="dropzone" class:dropping={dropping} class:uploading={progress != null} class:error={error} on:click={dismiss}>
	{#if error}
		<span class="text-danger">
			Upload failed.<br>
			Try again or use the upload button.
		</span>
	{:else if progress != null}
		{progress}%
	{:else} 
		<span><span class="iconify" data-icon="ic:baseline-file-upload" data-inline="false"></span></span>
	{/if}
</div>