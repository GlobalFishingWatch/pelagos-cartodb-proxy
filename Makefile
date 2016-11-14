# If no arguments are given, use the gcloud setup
_user=$(shell google-cloud-sdk/bin/gcloud config list | grep account | sed -e "s+.*= ++g")
_application=$(shell google-cloud-sdk/bin/gcloud config list | grep project | sed -e "s+.*= ++g")
_version=$(shell git symbolic-ref HEAD | sed -e "s+refs/heads/++g")
_client_version=$(shell git rev-parse HEAD)
_adminport=8000
_devport=8080

# Parse arguments
ifeq ($(user),)
	user=${_user}
else
	user=$(user)
endif
ifeq ($(application),)
	application=${_application}
else
	application=$(application)
endif
ifeq ($(version),)
	version=${_version}
else
	version=$(version)
endif
ifeq ($(shell whoami),vagrant)
	devhost=0.0.0.0
else
	devhost=127.0.0.1
endif

_test:
	echo ${user}
	echo ${application}
	echo ${version}


SHELL=/bin/bash

.PHONY: all apt-prerequisites prerequisites build build-gae gcloud deps gae/virtualenvloader/gaevirtualenv dependencies junk-clean upload-gae upload clean dev-server

all: build

deps:
	test -e $@ || virtualenv $@
	unset VIRTUAL_ENV; source $@/bin/activate; pip install --upgrade pip; pip install -r requirements.txt

gae/virtualenvloader/gaevirtualenv:
	test -e $@ || virtualenv $@
	unset VIRTUAL_ENV; source $@/bin/activate; pip install --upgrade pip; pip install -r gae-requirements.txt

google_appengine/appcfg.py:
	curl -sLO https://storage.googleapis.com/appengine-sdks/featured/google_appengine_1.9.30.zip
	unzip -q google_appengine_1.9.30.zip
	rm google_appengine_1.9.30.zip

google-cloud-sdk/bin/gcloud google-cloud-sdk/bin/gsutil:
	curl -sLO https://dl.google.com/dl/cloudsdk/channels/rapid/google-cloud-sdk.tar.gz
	tar -xzf google-cloud-sdk.tar.gz; rm google-cloud-sdk.tar.gz
	cd google-cloud-sdk; ./install.sh --usage-reporting false --path-update false --command-completion false

dependencies: deps gae/virtualenvloader/gaevirtualenv google_appengine/appcfg.py google-cloud-sdk/bin/gcloud

apt-prerequisites:
	sudo apt-get update
	sudo apt-get install -y zip git python-pip python-virtualenv python-dev build-essential libffi-dev libjpeg-dev pwgen

prerequisites: apt-prerequisites

junk-clean:
	find . -name "*.pyc" -o -name "*~" | while read name; do rm "$$name"; done

build-gae: gae/app.yaml dependencies junk-clean

build: build-gae

upload-gae: google_appengine/appcfg.py build-gae
	#google_appengine/appcfg.py update -A $(application) -V $(version) gae
	google-cloud-sdk/bin/gcloud preview app deploy ./gae/app.yaml --project "$(application)" --version "$(version)"

upload: upload-gae

clean: clean-deps

clean-deps:
	rm -rf deps
	rm -rf gae/virtualenvloader/gaevirtualenv

dev-server: dependencies
	cd gae; export PATH="../google_appengine:$$PATH"; dev_appserver.py . --host $(devhost) --port $(_devport) --admin_host $(devhost) --admin_port $(_adminport) -A $(_application) --datastore_path /tmp/dev_app_server_datastore --datastore_consistency_policy consistent

test: google_appengine/appcfg.py dependencies
	unset VIRTUAL_ENV; source deps/bin/activate; cd gae; nosetests --with-gae --gae-lib-root="../google_appengine"

deploy: build test upload
