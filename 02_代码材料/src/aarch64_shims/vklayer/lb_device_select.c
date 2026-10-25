/* VK_LAYER_LB_device_select -- tiny Vulkan layer for GH200 + SAPIEN's CPU-only aarch64 build.
 * 1) Exposes only the GPU picked by CUDA_VISIBLE_DEVICES (first token; integer index in PCI-domain order
 *    = nvidia-smi order, or a "GPU-<uuid>"), because the NVIDIA Vulkan driver ignores CUDA_VISIBLE_DEVICES.
 * 2) Reports pciDomain := pciBus. SAPIEN/svulkan2 without CUDA interop match a "pci:DDDD:BB:..." hint by
 *    comparing only the leading hex field against the bus number; on GH200 every GPU is bus 01 with a
 *    non-zero domain (0009/0019/...), so the match always fails ("Failed to find a supported physical device").
 * Enable with: VK_LAYER_PATH=<dir of json> VK_INSTANCE_LAYERS=VK_LAYER_LB_device_select */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>
#include <vulkan/vk_layer.h>

#define EXPORT __attribute__((visibility("default")))
static PFN_vkGetInstanceProcAddr next_gipa;
static PFN_vkEnumeratePhysicalDevices next_epd;
static PFN_vkGetPhysicalDeviceProperties2 next_gpdp2;
static PFN_vkGetPhysicalDeviceProperties2KHR next_gpdp2khr;
static PFN_vkGetDeviceProcAddr next_gdpa;

static void info(VkPhysicalDevice pd, uint32_t *domain, uint8_t uuid[VK_UUID_SIZE]) {
  VkPhysicalDevicePCIBusInfoPropertiesEXT pci = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PCI_BUS_INFO_PROPERTIES_EXT};
  VkPhysicalDeviceIDProperties id = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_ID_PROPERTIES, &pci};
  VkPhysicalDeviceProperties2 p = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, &id};
  next_gpdp2(pd, &p);
  *domain = pci.pciDomain;
  memcpy(uuid, id.deviceUUID, VK_UUID_SIZE);
}

static int select_index(VkPhysicalDevice *all, uint32_t n) {
  const char *cvd = getenv("CUDA_VISIBLE_DEVICES");
  if (!cvd || !*cvd || n <= 1) return -1;
  char tok[128]; size_t k = strcspn(cvd, ","); if (k >= sizeof tok) k = sizeof tok - 1;
  memcpy(tok, cvd, k); tok[k] = 0;
  uint32_t dom[64]; uint8_t uu[64][VK_UUID_SIZE];
  if (n > 64) n = 64;
  for (uint32_t i = 0; i < n; i++) info(all[i], &dom[i], uu[i]);
  if (!strncmp(tok, "GPU-", 4)) {  /* uuid form: GPU-xxxxxxxx-xxxx-... */
    for (uint32_t i = 0; i < n; i++) {
      char s[40]; const uint8_t *u = uu[i];
      snprintf(s, sizeof s, "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
               u[0],u[1],u[2],u[3],u[4],u[5],u[6],u[7],u[8],u[9],u[10],u[11],u[12],u[13],u[14],u[15]);
      if (!strncmp(tok + 4, s, strlen(tok + 4))) return (int)i;
    }
    return -1;
  }
  char *end; long want = strtol(tok, &end, 10);
  if (*end || want < 0 || want >= (long)n) return -1;
  for (uint32_t i = 0; i < n; i++) {  /* rank by PCI domain */
    long r = 0;
    for (uint32_t j = 0; j < n; j++) if (dom[j] < dom[i]) r++;
    if (r == want) return (int)i;
  }
  return -1;
}

static VKAPI_ATTR VkResult VKAPI_CALL lb_EnumeratePhysicalDevices(VkInstance inst, uint32_t *count, VkPhysicalDevice *out) {
  uint32_t n = 0;
  VkResult r = next_epd(inst, &n, NULL);
  if (r != VK_SUCCESS || n == 0) return next_epd(inst, count, out);
  VkPhysicalDevice *all = malloc(n * sizeof *all);
  next_epd(inst, &n, all);
  int sel = select_index(all, n);
  if (sel < 0) { free(all); return next_epd(inst, count, out); }
  if (!out) { *count = 1; free(all); return VK_SUCCESS; }
  if (*count < 1) { free(all); return VK_INCOMPLETE; }
  out[0] = all[sel]; *count = 1;
  if (getenv("LB_VK_DEBUG")) fprintf(stderr, "[lb_device_select] CUDA_VISIBLE_DEVICES=%s -> vk device %d of %u\n", getenv("CUDA_VISIBLE_DEVICES"), sel, n);
  free(all);
  return VK_SUCCESS;
}

static void patch(VkPhysicalDeviceProperties2 *p) {
  for (VkBaseOutStructure *s = (VkBaseOutStructure *)p->pNext; s; s = s->pNext)
    if (s->sType == VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PCI_BUS_INFO_PROPERTIES_EXT) {
      VkPhysicalDevicePCIBusInfoPropertiesEXT *pci = (VkPhysicalDevicePCIBusInfoPropertiesEXT *)s;
      pci->pciDomain = pci->pciBus;
    }
}
static VKAPI_ATTR void VKAPI_CALL lb_GetPhysicalDeviceProperties2(VkPhysicalDevice pd, VkPhysicalDeviceProperties2 *p) {
  next_gpdp2(pd, p); patch(p);
}
static VKAPI_ATTR void VKAPI_CALL lb_GetPhysicalDeviceProperties2KHR(VkPhysicalDevice pd, VkPhysicalDeviceProperties2 *p) {
  (next_gpdp2khr ? next_gpdp2khr : next_gpdp2)(pd, p); patch(p);
}

static VKAPI_ATTR VkResult VKAPI_CALL lb_CreateInstance(const VkInstanceCreateInfo *ci, const VkAllocationCallbacks *a, VkInstance *inst) {
  VkLayerInstanceCreateInfo *l = (VkLayerInstanceCreateInfo *)ci->pNext;
  while (l && !(l->sType == VK_STRUCTURE_TYPE_LOADER_INSTANCE_CREATE_INFO && l->function == VK_LAYER_LINK_INFO))
    l = (VkLayerInstanceCreateInfo *)l->pNext;
  if (!l) return VK_ERROR_INITIALIZATION_FAILED;
  PFN_vkGetInstanceProcAddr gipa = l->u.pLayerInfo->pfnNextGetInstanceProcAddr;
  l->u.pLayerInfo = l->u.pLayerInfo->pNext;
  PFN_vkCreateInstance create = (PFN_vkCreateInstance)gipa(VK_NULL_HANDLE, "vkCreateInstance");
  VkResult r = create(ci, a, inst);
  if (r != VK_SUCCESS) return r;
  next_gipa = gipa;
  next_epd = (PFN_vkEnumeratePhysicalDevices)gipa(*inst, "vkEnumeratePhysicalDevices");
  next_gpdp2 = (PFN_vkGetPhysicalDeviceProperties2)gipa(*inst, "vkGetPhysicalDeviceProperties2");
  next_gpdp2khr = (PFN_vkGetPhysicalDeviceProperties2KHR)gipa(*inst, "vkGetPhysicalDeviceProperties2KHR");
  return VK_SUCCESS;
}

static VKAPI_ATTR VkResult VKAPI_CALL lb_CreateDevice(VkPhysicalDevice pd, const VkDeviceCreateInfo *ci, const VkAllocationCallbacks *a, VkDevice *dev) {
  VkLayerDeviceCreateInfo *l = (VkLayerDeviceCreateInfo *)ci->pNext;
  while (l && !(l->sType == VK_STRUCTURE_TYPE_LOADER_DEVICE_CREATE_INFO && l->function == VK_LAYER_LINK_INFO))
    l = (VkLayerDeviceCreateInfo *)l->pNext;
  if (!l) return VK_ERROR_INITIALIZATION_FAILED;
  PFN_vkGetInstanceProcAddr gipa = l->u.pLayerInfo->pfnNextGetInstanceProcAddr;
  next_gdpa = l->u.pLayerInfo->pfnNextGetDeviceProcAddr;
  l->u.pLayerInfo = l->u.pLayerInfo->pNext;
  PFN_vkCreateDevice create = (PFN_vkCreateDevice)gipa(VK_NULL_HANDLE, "vkCreateDevice");
  return create(pd, ci, a, dev);
}

EXPORT VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL lb_GetDeviceProcAddr(VkDevice dev, const char *name) {
  if (!strcmp(name, "vkGetDeviceProcAddr")) return (PFN_vkVoidFunction)lb_GetDeviceProcAddr;
  return next_gdpa(dev, name);
}

EXPORT VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL lb_GetInstanceProcAddr(VkInstance inst, const char *name) {
#define HOOK(fn) if (!strcmp(name, "vk" #fn)) return (PFN_vkVoidFunction)lb_##fn;
  HOOK(GetInstanceProcAddr) HOOK(CreateInstance) HOOK(EnumeratePhysicalDevices)
  HOOK(GetPhysicalDeviceProperties2) HOOK(GetPhysicalDeviceProperties2KHR) HOOK(CreateDevice) HOOK(GetDeviceProcAddr)
  return next_gipa ? next_gipa(inst, name) : NULL;
}

EXPORT VKAPI_ATTR VkResult VKAPI_CALL vkNegotiateLoaderLayerInterfaceVersion(VkNegotiateLayerInterface *v) {
  if (v->loaderLayerInterfaceVersion > 2) v->loaderLayerInterfaceVersion = 2;
  v->pfnGetInstanceProcAddr = lb_GetInstanceProcAddr;
  v->pfnGetDeviceProcAddr = lb_GetDeviceProcAddr;
  v->pfnGetPhysicalDeviceProcAddr = NULL;
  return VK_SUCCESS;
}
