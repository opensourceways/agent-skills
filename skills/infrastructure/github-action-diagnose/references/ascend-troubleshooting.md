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

Driver/hardware failure keywords in logs:
- `ERR99999`: General NPU driver error.
- `error code 507035`: NPU device initialization failure.
- `Device not found`: NPU not recognized by driver.

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

## 5. K8s Runner Logs
Key strings to search for:
- **Runner version v2.330.0 is deprecated and cannot receive messages**: github action runner exits for its version is deprecated

## 6. OOM / Resource Overflow
- `Killed`: system-level OOM kill signal.
- `Bus error`: insufficient shared memory (SHM).
- `No space left on device`: disk full.

## 7. Multi-node Cascading Timeout
When a multi-node job reports `Timeout`, identify the Master node first — it is the most likely root cause.

Master node identification:
- Check `RANK_TABLE_FILE` for the node with `rank_id=0`.
- Search logs for `master_addr` / `MASTER_ADDR` environment variable.
- Confirm whether the Master node has `Unexpected Exit` or driver errors.

## 8. Node Network Failure (出口网络故障)

When a runner node has degraded or broken external network connectivity, symptoms appear during dependency installation or artifact download steps — not in NPU-related steps.

### Identification Signals

| curl Error | Code | Description |
|---|---|---|
| `SSL connection timeout` | 28 | SSL handshake blocked; 0 bytes transferred over minutes |
| `HTTP/2 stream 0 was not closed cleanly: PROTOCOL_ERROR (err 1)` | 92 | Connection reset by server/proxy after partial download |
| `Could not resolve host` | 6 | DNS resolution failure |

### Precursor Pattern
- Download speed consistently < 50 KB/s for multi-MB files throughout the job (visible in wget/curl progress output)
- Example: a 2.35 MB file taking 4+ minutes at 8–14 KB/s before the final curl failure

### Differentiation from Code Issues
- Failure is in a `curl`/`wget`/`pip` download command, not a Python traceback or test assertion
- Other concurrent jobs on different runner nodes complete the same installation steps successfully in the same Run
- Error codes are OS-level (curl exit codes), not Python exceptions

### Node Tracing
Apply the standard Step 2a node tracing procedure. If multiple failing jobs share the same runner name prefix (same node pool), the fault is pool-level rather than isolated to a single node.
