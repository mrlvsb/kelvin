<script>
export let size = 60;
export let color = '#FF3E00';
export let unit = 'px';

const range = (size, startAt = 0) => [...Array(size).keys()].map((i) => i + startAt);
</script>

<div class="wrapper" style="--size:{size}{unit}">
  {#each range(3, 1) as i}
    <div
      class="dot"
      style="--dotSize:{size * 0.25}{unit}; --color:{color}; animation-delay:  {i * 0.07}s;">
    </div>
  {/each}
</div>

<style>
.wrapper {
  height: var(--size);
  width: var(--size);
  display: flex;
  align-items: center;
  justify-content: center;
}
.dot {
  height: var(--dotSize);
  width: var(--dotSize);
  background-color: var(--color);
  margin: 2px;
  display: inline-block;
  border-radius: 100%;
  animation: sync 0.6s ease-in-out infinite alternate both running;
}
@-webkit-keyframes sync {
  33% {
    -webkit-transform: translateY(10px);
    transform: translateY(10px);
  }
  66% {
    -webkit-transform: translateY(-10px);
    transform: translateY(-10px);
  }
  100% {
    -webkit-transform: translateY(0);
    transform: translateY(0);
  }
}
@keyframes sync {
  33% {
    -webkit-transform: translateY(10px);
    transform: translateY(10px);
  }
  66% {
    -webkit-transform: translateY(-10px);
    transform: translateY(-10px);
  }
  100% {
    -webkit-transform: translateY(0);
    transform: translateY(0);
  }
}
</style>
