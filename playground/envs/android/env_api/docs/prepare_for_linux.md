### Prepare Docker on linux(x86_64)

1. Install Docker on your machine. Make sure your machine already supports KVM. You can use the following code to check
   if your machine supports kvm:

```bash
apt-get install cpu-checker
kvm-ok
```

Meanwhile, ensure that your terminal has permission to start Docker. You can set it through the following code:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

2. Download related docker files on link: https://drive.google.com/file/d/1SJ79gdO7whgUod3HnuS87aOKihRk1i-U/view?usp=drive_link

3. To create docker, run:

```bash
mkdir docker_file
cd docker_file
unzip /path/to/your/docker-file.zip
cd docker-file
docker build -t android_eval:latest .
```

Note that we use
```bash
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

to speed up download speed, you can replace it to your source if needed or just delete it.
