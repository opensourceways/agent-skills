# Ascend NPU K8s Troubleshooting Reference

## 1. Resource Saturation Patterns
When NPUs are fully utilized, Pods will remain in `Pending` state.

### Check Allocatable NPUs
```bash
kubectl get nodes -o custom-columns=NAME:.metadata.name,NPU_ALLOCATABLE:.status.allocatable.huawei\.com/ascend-910,NPU_CAPACITY:.status.capacity.huawei\.com/ascend-910
```

### Describe Pod Error
Look for:
- `Insufficient huawei.com/ascend-910`
- `Insufficient huawei.com/ascend-310p`

## 2. NPU Health Status (npu-smi)
Standard output of `npu-smi info`:

| Field | Interpretation |
|---|---|
| Health | "OK" is normal. "Alarm" or "Failure" requires hardware check. |
| HBM Usage | If near 100%, memory fragmentation or leakage may occur. |
| Temp | Should be < 80°C typically. High temp leads to frequency reduction. |

## 3. Kernel & Driver Logs (dmesg)
Key strings to search for:
- `hiai: npu heartbeat loss`: Hardware/Firmware crash.
- `PCIE Error`: Connection issue between CPU and NPU.
- `task timeout`: Calculation hung.

## 4. K8s Device Plugin Logs
Check if the plugin is reporting issues:
```bash
kubectl logs -n kube-system -l app=ascend-device-plugin
```
Look for:
- `get npu device count failed`
- `npu device is unhealthy`
