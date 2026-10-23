<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import { careBreadcrumbs, type CareNavigationContext } from '@/utils/careNavigation'
const props = defineProps<{ context?: CareNavigationContext }>()
const route = useRoute()
const items = computed(() => careBreadcrumbs(route.name, props.context))
</script>
<template>
  <nav class="care-navigation" aria-label="Ruta actual">
    <ol>
      <li v-for="(item, index) in items" :key="index">
        <el-icon v-if="index" aria-hidden="true"><ArrowRight /></el-icon>
        <router-link v-if="item.to" :to="item.to">{{ item.label }}</router-link>
        <span v-else :aria-current="index === items.length - 1 ? 'page' : undefined">{{
          item.label
        }}</span>
      </li>
    </ol>
  </nav>
</template>
<style scoped>
.care-navigation {
  margin-bottom: 20px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
}
ol {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 8px;
  padding: 0;
  margin: 0;
  list-style: none;
}
li {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
}
.el-icon {
  flex-shrink: 0;
  font-size: 12px;
}
a,
span {
  min-width: 0;
  min-height: 32px;
  box-sizing: border-box;
  padding: 4px 8px;
  align-content: center;
  border-radius: 4px;
  overflow-wrap: anywhere;
}
a {
  text-decoration: underline;
  text-underline-offset: 4px;
}
a:hover {
  background: var(--el-color-primary-light-9);
}
[aria-current='page'] {
  color: var(--care-link-color);
  background: var(--el-color-primary-light-9);
  font-weight: 600;
}
@media (max-width: 600px) {
  a,
  span {
    min-height: 44px;
  }
}
</style>
