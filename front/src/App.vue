<template>
  <div class="app">
    <router-view v-slot="{ Component }">
      <template v-if="$route.meta.keepAlive">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </template>
      <template v-else>
        <component :is="Component" />
      </template>
    </router-view>
  </div>
</template>

<script setup>
// App.vue 作为根组件
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  font-size: 16px;
  height: 100%;
  width: 100%;
}

.app {
  max-width: 750px;
  margin: 0 auto;
  height: 100%;
}

/* 移动端适配 */
@media screen and (max-width: 750px) {
  html {
    font-size: calc(100vw / 750 * 16);
  }
}
</style>
