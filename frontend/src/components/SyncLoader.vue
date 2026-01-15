<script lang="ts" setup>
defineProps({
  size: {
    type: Number,
    default: 60
  },
  color: {
    type: String,
    default: '#FF3E00'
  },
  unit: {
    type: String,
    default: 'px'
  }
});

const range = (size, startAt = 0) => [...Array(size).keys()].map((i) => i + startAt);
</script>

<template>
  <div class="wrapper" :style="`--size:${size}${unit}`">
    <div
      v-for="i in range(3, 1)"
      :key="i"
      class="dot"
      :style="`--dotSize:${size * 0.25}${unit}; --color:${color}; animation-delay:${i * 0.07}s;`"
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
