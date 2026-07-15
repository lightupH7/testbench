import type { RouteRecordRaw } from "vue-router";

const routes: RouteRecordRaw[] = [
  {
    path: "/",
    component: () => import("@/layouts/MainLayout.vue"),
    children: [
      { path: "", component: () => import("@/pages/IndexPage.vue") },
      {
        path: "manual",
        redirect: "/monitor"
      },
      {
        path: "upload",
        component: () => import("@/pages/UploadPage.vue"),
        meta: { keepAlive: true }
      },
      {
        path: "automation",
        component: () => import("@/pages/AutomationPage.vue"),
        meta: { keepAlive: true }
      },
      {
        path: "records",
        component: () => import("@/pages/TestRecordsPage.vue"),
        meta: { keepAlive: true }
      },
      {
        path: "monitor",
        component: () => import("@/pages/MonitorPage.vue"),
        meta: { keepAlive: true }
      },
      {
        path: "scope",
        component: () => import("@/pages/ScopeDebugPage.vue"),
        meta: { keepAlive: true }
      }
    ]
  },

  // Always leave this as last one,
  // but you can also remove it
  {
    path: "/:catchAll(.*)*",
    component: () => import("@/pages/ErrorNotFound.vue")
  }
];

export default routes;
