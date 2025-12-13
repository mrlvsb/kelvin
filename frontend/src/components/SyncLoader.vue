<script setup lang="ts">
/**
 * Component that displays three orange dots loading indicator
 */
const size: number = 60;
const color: string = '#FF3E00';
</script>

<template>
  <div class="wrapper" :style="`--size: ${size}px`">
    <div
      v-for="i in 3"
      :key="i"
      class="dot"
      :style="`--dotSize:${size * 0.25}px; --color:${color}; animation-delay:  ${i * 0.07}s;`"
    ></div>
  </div>
</template>

<style scoped>
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
