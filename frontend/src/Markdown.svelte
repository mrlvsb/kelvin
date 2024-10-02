<script>
import { safeMarkdown } from './markdown.js';
export let content;
</script>

<div class="md">{@html safeMarkdown(content, { breaks: false })}</div>

<style>
:global(.md h1) {
  font-size: 1.5rem;
}
:global(.md h2) {
  font-size: 1.4rem;
}
:global(.md h3) {
  font-size: 1.3rem;
}
:global(.md h4) {
  font-size: 1.2rem;
}
:global(.md h5) {
  font-size: 1.1rem;
}
:global(.md h6) {
  font-size: 1rem;
}
</style>
