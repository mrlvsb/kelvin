<script setup lang="ts">
//import HelloWorld from './components/HelloWorld.vue'
//import ClassDetail from "./ClassDetail.vue"
//import VueRouter from "vue-router";
import ClassList from "./ClassList.vue";
import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap/dist/js/bootstrap.min.js'
</script>

<template>
      <!--<p>-->
      <!-- use the router-link component for navigation. -->
      <!-- specify the link by passing the `to` prop. -->
      <!-- `<router-link>` will render an `<a>` tag with the correct `href` attribute -->
      <!--
      <router-link to="/">Go to Home</router-link> |
      <router-link to="/about">Go to About</router-link>
      </p>
      -->

      <!-- route outlet -->
      <!-- component matched by the route will render here -->
      <router-view></router-view>

  <!--<HelloWorld msg="Vite + Vue" />-->
  <!--<ClassDetail/>-->
      <ClassList/>
</template>


<style scoped>
</style>

