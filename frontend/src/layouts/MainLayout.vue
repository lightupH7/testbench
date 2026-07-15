<template>
  <q-layout view="hHh Lpr lFf" class="app-shell">
    <q-drawer show-if-above bordered :width="248" class="app-sidebar">
      <div class="sidebar-brand">
        <div class="sidebar-brand__kicker">TestBench</div>
        <div class="sidebar-brand__title">FPGA Debug UI</div>
      </div>

      <q-list class="sidebar-nav" padding>
        <q-item
          v-for="item in navItems"
          :key="item.to"
          clickable
          :to="item.to"
          exact
          active-class="sidebar-item--active"
          class="sidebar-item"
        >
          <q-item-section avatar>
            <q-icon :name="item.icon" size="20px" />
          </q-item-section>
          <q-item-section>{{ item.label }}</q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <q-page-container class="app-content">
      <router-view v-slot="{ Component, route }">
        <keep-alive>
          <component
            :is="Component"
            v-if="route.meta.keepAlive"
            :key="route.fullPath"
          />
        </keep-alive>
        <component
          :is="Component"
          v-if="!route.meta.keepAlive"
          :key="route.fullPath"
        />
      </router-view>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
const navItems = [
  { label: "主页面", to: "/", icon: "home" },
  { label: "上传文件", to: "/upload", icon: "upload_file" },
  { label: "自动化测试", to: "/automation", icon: "fact_check" },
  { label: "测试记录", to: "/records", icon: "history" },
  { label: "控制台", to: "/monitor", icon: "terminal" },
  { label: "示波器调试", to: "/scope", icon: "monitor_heart" }
];
</script>
