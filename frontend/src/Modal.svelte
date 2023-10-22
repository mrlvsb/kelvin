<script>
import {fade, fly} from "svelte/transition";
import {quintOut} from "svelte/easing";

export let open = false;
export let showBackdrop = true;
export let onClosed;
export let title = '';
export let cancelButtonLabel = 'Cancel';
export let proceedButtonLabel = 'Proceed';

function modalClose(data) {
	open = false;
	if (onClosed)
		onClosed(data);
}
</script>

<style>
.modal {
	display: block;
}
</style>

{#if open}
	<div class="modal" id="kelvin-modal" tabindex="-1" role="dialog" aria-labelledby="Modal" aria-hidden={false}>
		<div class="modal-dialog" role="document" in:fly={{ y: -50, duration: 300 }} out:fly={{ y: -50, duration: 300, easing: quintOut }}>
			<div class="modal-content">
				<div class="modal-header">
					<h5 class="modal-title" id="sampleModalLabel">{title}</h5>
					<button type="button" class="btn-close" data-dismiss="modal" aria-label="Close" on:click={() => modalClose(false)}></button>
				</div>
				<div class="modal-body">
					<slot></slot>
				</div>
				<div class="modal-footer">
					<button type="button" class="btn btn-secondary" data-dismiss="modal" on:click={() => modalClose(false)}>{cancelButtonLabel}</button>
					<button type="button" class="btn btn-primary" on:click={() => modalClose(true)}>{proceedButtonLabel}</button>
				</div>
			</div>
		</div>
	</div>
	{#if showBackdrop}
		<div class="modal-backdrop show" transition:fade={{ duration: 150 }} />
	{/if}
{/if}
