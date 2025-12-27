#!/usr/bin/env python3
"""
Helper script to display network IP addresses for testing web apps on mobile devices.
"""
import socket
import subprocess
import sys

def get_network_ip():
    """Get the local network IP address."""
    try:
        # Create a socket to get the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to a public DNS server (doesn't actually send data)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

def get_all_ips():
    """Get all network interfaces and their IPs."""
    ips = []
    try:
        # Try using 'ip' command on Linux
        result = subprocess.run(['ip', 'addr', 'show'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if 'inet ' in line and '127.0.0.1' not in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        ip = parts[1].split('/')[0]
                        ips.append(ip)
    except Exception:
        pass
    
    if not ips:
        # Fallback to socket method
        ip = get_network_ip()
        if ip:
            ips.append(ip)
    
    return ips

def main():
    print("=" * 60)
    print("🌐 Travelland - Network Access Information")
    print("=" * 60)
    print()
    
    ips = get_all_ips()
    
    if not ips:
        print("⚠️  Could not detect network IP address.")
        print("   Make sure you're connected to a network (WiFi or Ethernet)")
        print()
        return
    
    print("📱 To test on your iPhone:")
    print()
    print("1. Make sure your iPhone is on the SAME WiFi network as this computer")
    print()
    print("2. On your iPhone, open Safari and navigate to:")
    print()
    
    for ip in ips:
        print(f"   City Guides:    http://{ip}:5010")
        print(f"   Hotel Finder:   http://{ip}:5000")
        print()
    
    print("3. The apps should load and be fully functional on your iPhone")
    print()
    print("=" * 60)
    print()
    print("🚀 Start the apps:")
    print()
    print("   For City Guides:")
    print("   cd city-guides && python app.py")
    print()
    print("   For Hotel Finder:")
    print("   cd hotel-finder && python app.py")
    print()
    print("=" * 60)

if __name__ == '__main__':
    main()
