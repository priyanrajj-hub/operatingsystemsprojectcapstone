#!/bin/bash
# check_topology.sh

echo "[*] Checking Linux kernel for hybrid core presence..."
sys_core_type_files=$(ls /sys/devices/system/cpu/cpu*/topology/core_type 2>/dev/null)

if [ -n "$sys_core_type_files" ]; then
    echo -e "\033[0;32m[+] SUCCESS:\033[0m /sys topology/core_type found. Native hybrid routing is fully supported."
    echo ""
    echo "Summary of P-Cores vs E-Cores (0=P-Core, 1=E-Core):"
    
    for file in $sys_core_type_files; do
        cpu_id=$(echo $file | awk -F'/' '{print $6}')
        type=$(cat $file)
        if [ "$type" -eq 0 ]; then
            echo -e "  $cpu_id -> \033[1;36mP-Core\033[0m"
        else
            echo -e "  $cpu_id -> \033[1;33mE-Core\033[0m"
        fi
    done
else
    echo -e "\033[0;31m[-] FAILURE:\033[0m core_type does not exist. The kernel is too old or hardware lacks hybrid architecture."
    echo ""
    echo "[*] Polling using lscpu -e as manual fallback visualization:"
    lscpu -e
fi
