import { api } from "@/lib/api";

function urlB64ToUint8Array(b64) {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const s = (b64 + pad).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(s);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export function pushSupported() {
  return typeof navigator !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export async function enablePush() {
  const reg = await navigator.serviceWorker.register("/push-sw.js");
  const perm = await Notification.requestPermission();
  if (perm !== "granted") throw new Error("Permission denied");
  const { data } = await api.get("/push/vapid-public-key");
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToUint8Array(data.key) });
  }
  await api.post("/push/subscribe", sub.toJSON());
  await api.post("/push/test");
  return true;
}
