<script setup lang="ts">
type Brambora = {
  name: string;
  age: number;
};

const test = 'Ahoj';

const brambora = {
  name: 'Brambora',
  age: 10
} satisfies Brambora;

console.log(brambora, test);
</script>

<template>
  <div>
    <h1>Hello World</h1>
    <h2 class="random">Test</h2>
  </div>
</template>

<style scoped>
div {
  background-color: red;
  width: 400px;
  aspect-ratio: 1 / 1;
}

h1 {
  color: pink;
  font-weight: bold;
}

.random {
  color: blue;
}
</style>
