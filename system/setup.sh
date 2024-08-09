# Function to display the help message
help() {
    echo "Usage: setup.sh [command]"
    echo "Commands:"
    echo "  help: Display this help message"
    echo "  systemd: Setup the systemd service"
    echo "  install: Install the system dependencies"
}

# Function to install the python dependencies
install() {
    echo "Installing system dependencies..."
    sudo apt-get update
    sudo apt-get install -y vim git bc libncurses5-dev bison flex libssl-dev raspberrypi-kernel-headers ffmpeg nginx python3 python3-dev python3-pip python3-venv
    sudo mount -t debugfs debugs /sys/kernel/debug
    git clone https://github.com/PaulCreaser/rpi-i2s-audio
    cd rpi-i2s-audio
    # Edit the my_loader.c to reconfigure the i2s mode
    # Replace the configuration for the MCLK accordingly
    #.daifmt = SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF | SND_SOC_DAIFMT_CBS_CFS,
    #↓
    #.daifmt = SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF | SND_SOC_DAIFMT_CBM_CFM,
    sed -i 's/\.daifmt = SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF | SND_SOC_DAIFMT_CBS_CFS,/\.daifmt = SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF | SND_SOC_DAIFMT_CBM_CFM,/' my_loader.c
    make -C /lib/modules/$(uname -r )/build M=$(pwd) modules
    sudo insmod my_loader.ko
    sudo cp my_loader.ko /lib/modules/$(uname -r)
    echo 'my_loader' | sudo tee --append /etc/modules > /dev/null
    sudo depmod -a
    sudo modprobe my_loader
    # Uncomment dtparam=i2s=on from /boot/firmware/config.txt
    sudo sed -i 's/#dtparam=i2s=on/dtparam=i2s=on/' /boot/firmware/config.txt
    # Enable GPIO 25 for act led
    echo "dtparam=act_led_gpio=25" | sudo tee --append /boot/firmware/config.txt > /dev/null
    # Generate certificates for nginx and create directory beforehand
    sudo mkdir -p /etc/nginx/ssl
    sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/nginx/ssl/nginx.key -out /etc/nginx/ssl/nginx.crt
    # Copy nginx config to sites-enabled and reload the service, overwrite the existing config
    sudo cp nginx/default /etc/nginx/sites-enabled/default
    sudo systemctl reload nginx
}

systemd() {
    echo "Setting up systemd service..."
    sudo cp systemd/* /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now phone_interface
    sudo systemctl enable --now phone_server
    sudo systemctl enable --now phone_automount
}

# Check if the user has provided a command
if [ $# -eq 0 ]; then
    echo "Error: No command provided"
    help
    exit 1
fi

# Check the command provided by the user
case $1 in
    help)
        help
        ;;
    install)
        install
        ;;
    systemd)
        systemd
        ;;
    *)
        echo "Error: Invalid command"
        help
        exit 1
        ;;
esac

exit 0