#!/bin/bash

# Configurable variables
CHECK_INTERVAL=10  # Check interval in seconds
DEVICE="/dev/sda1"
MOUNT_POINT="/mnt/usb"
SOURCE_DIR="/home/pi/weddingRingManager/server/recordings"
DEST_DIR="$MOUNT_POINT/recordings"

# Function to check if the device is mounted
is_mounted() {
    mountpoint -q "$MOUNT_POINT"
    return $?
}

# Function to check if the mount point is read-only
is_mounted_readonly() {
    mount | grep "$MOUNT_POINT" | grep -q "ro,"
    return $?
}

# Function to perform a filesystem check
check_filesystem() {
    echo "Running filesystem check on $DEVICE..."
    sudo fsck -y "$DEVICE"
    if [ $? -ne 0 ]; then
        echo "Filesystem check failed"
        return 1
    fi
    echo "Filesystem check completed successfully"
    return 0
}

# Function to mount the device
mount_device() {
    if ! is_mounted; then
        echo "Mounting $DEVICE to $MOUNT_POINT..."
        sudo mount "$DEVICE" "$MOUNT_POINT"
        if [ $? -ne 0 ]; then
            echo "Failed to mount $DEVICE"
            return 1
        fi
        echo "$DEVICE mounted successfully"
    else
        echo "$DEVICE is already mounted"
    fi

    # Check if the mount is read-only and attempt to remount as read-write
    if is_mounted_readonly; then
        echo "$MOUNT_POINT is mounted as read-only, attempting to remount as read-write..."
        sudo mount -o remount,rw "$MOUNT_POINT"
        if [ $? -ne 0 ]; then
            echo "Failed to remount $MOUNT_POINT as read-write"
            return 1
        fi
        echo "$MOUNT_POINT remounted as read-write successfully"
    fi

    return 0
}

# Function to unmount the device
unmount_device() {
    if is_mounted; then
        echo "Unmounting $DEVICE from $MOUNT_POINT..."
        sudo umount "$MOUNT_POINT"
        if [ $? -ne 0 ]; then
            echo "Failed to unmount $DEVICE"
            return 1
        fi
        echo "$DEVICE unmounted successfully"
    else
        echo "$DEVICE is not mounted"
    fi
    return 0
}

# Function to perform the rsync job
sync_files() {
    echo "Syncing files from $SOURCE_DIR to $DEST_DIR..."
    mkdir -p "$DEST_DIR"
    rsync -av --delete "$SOURCE_DIR/" "$DEST_DIR/"
    if [ $? -eq 0 ]; then
        echo "Files synced successfully"
    else
        echo "Failed to sync files"
    fi
}

# Main loop
while true; do
    if [ -e "$DEVICE" ]; then
        echo "$DEVICE exists"
        check_filesystem
        if [ $? -eq 0 ]; then
            mount_device
            if [ $? -eq 0 ]; then
                sync_files
            fi
        fi
    else
        echo "$DEVICE does not exist"
        unmount_device
    fi
    echo "Sleeping for $CHECK_INTERVAL seconds..."
    sleep "$CHECK_INTERVAL"
done