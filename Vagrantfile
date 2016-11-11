# -*- mode: ruby -*-
# vi: set ft=ruby :
Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/precise64"

  # Forward server port
  config.vm.network :forwarded_port, host: 8000, guest: 8000, auto_correct: true
  config.vm.network :forwarded_port, host: 8080, guest: 8080, auto_correct: true

  # Provision the development environment
  config.vm.provision :shell, privileged: false, inline: "cd /vagrant; make prerequisites"

  # Also install google cloud sdk
  config.vm.provision :shell, privileged: false, inline: <<-PROVISION
    # Install google cloud sdk
    if [[ ! -d ~/google-cloud-sdk ]]; then
      curl https://sdk.cloud.google.com | bash
    fi
  PROVISION
end
