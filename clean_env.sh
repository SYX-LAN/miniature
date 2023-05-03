docker rm -f $(docker ps -aq)
docker rmi $(sudo docker images -f "reference=kindest/node" -q)