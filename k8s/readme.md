Precisa ter instalado: docker, minicube, kubectl e helm

## Iniciar Minikube
minikube start --driver=docker

minikube addons enable ingress

minikube status

## Criar o namespace e aplicar o manifest

kubectl create namespace devops

kubectl apply -f k8s/secrets/
kubectl apply -f k8s/configmaps/
kubectl apply -f k8s/statefulsets/
kubectl apply -f k8s/services/
kubectl apply -f k8s/deployments/
kubectl apply -f k8s/ingress.yaml

## Verificar se roda e as 2 réplicas
kubectl get pods -n devops
kubectl get svc -n devops

## Acessar a aplicação no port-forward
kubectl port-forward -n devops svc/gateway 8000:8000
depois acessar: http://localhost:8000/health

## Acessar via NodePort
minikube service gateway -n devops --url

---

Instalar Prometheus e Grafana 

## verificar instalação
kubectl get pods -n devops -l "release=prometheus"

## Aplicar arquivo de observabilidade 
kubectl apply -f k8s/monitoring/working-services-monitors.yaml

## Acessar Prometheus
kubectl port-forward -n devops svc/prometheus-kube-prometheus-prometheus 9090:9090

acessar: http://localhost:9090, Status e depois target

## Acessar Grafana 
kubectl port-forward -n devops svc/prometheus-grafana 3000:80

acessar: http://localhost:3000, vá em explore dê query em matching_http_requests_total para ver as métricas customizadas do matching‑service, as outras em métricas padrão do Python python_gc_*

---



