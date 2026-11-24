```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: online-boutique
automountServiceAccountToken: false
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis-cart
  labels:
    app: redis-cart
spec:
  serviceName: redis-cart
  replicas: 1
  selector:
    matchLabels:
      app: redis-cart
  template:
    metadata:
      labels:
        app: redis-cart
    spec:
      containers:
        - name: redis
          image: redis:alpine
          ports:
            - name: redis
              containerPort: 6379
          securityContext:
            allowPrivilegeEscalation: false
            seccompProfile:
              type: RuntimeDefault
          readinessProbe:
            tcpSocket:
              port: 6379
            periodSeconds: 5
            timeoutSeconds: 5
          livenessProbe:
            tcpSocket:
              port: 6379
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
          volumeMounts:
            - name: redis-data
              mountPath: /data
  volumeClaimTemplates:
    - metadata:
        name: redis-data
      spec:
        accessModes:
          - ReadWriteOnce
        resources:
          requests:
            storage: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: redis-cart
spec:
  selector:
    app: redis-cart
  ports:
    - name: redis
      port: 6379
      targetPort: 6379
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: adservice
  labels:
    app: adservice
spec:
  replicas: 2
  selector:
    matchLabels:
      app: adservice
  template:
    metadata:
      labels:
        app: adservice
    spec:
      serviceAccountName: online-boutique
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: server
          image: us-central1-docker.pkg.dev/google-samples/microservices-demo/adservice:v0.10.3
          ports:
            - name: grpc
              containerPort: 9555
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          startupProbe:
            tcpSocket:
              port: 9555
            periodSeconds: 10
            failureThreshold: 30
            timeoutSeconds: 5
          readinessProbe:
            tcpSocket:
              port: 9555
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          livenessProbe:
            tcpSocket:
              port: 9555
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 3
          resources:
            requests:
              cpu: 200m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: adservice
spec:
  selector:
    app: adservice
  ports:
    - name: grpc
      port: 9555
      targetPort: 9555
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cartservice
  labels:
    app: cartservice
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cartservice
  template:
    metadata:
      labels:
        app: cartservice
    spec:
      serviceAccountName: online-boutique
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: server
          image: us-central1-docker.pkg.dev/google-samples/microservices-demo/cartservice:v0.10.3
          ports:
            - name: grpc
              containerPort: 7070
          env:
            - name: REDIS_ADDR
              value: "redis-cart:6379"
            - name: ASPNETCORE_HTTP_PORTS
              value: "7070"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          startupProbe:
            tcpSocket:
              port: 7070
            periodSeconds: 10
            failureThreshold: 30
            timeoutSeconds: 5
          readinessProbe:
            tcpSocket:
              port: 7070
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          livenessProbe:
            tcpSocket:
              port: 7070
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 3
          resources:
            requests:
              cpu: 200m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: cartservice
spec:
  selector:
    app: cartservice
  ports:
    - name: grpc
      port: 7070
      targetPort: 7070
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkoutservice
  labels:
    app: checkoutservice
spec:
  replicas: 2
  selector:
    matchLabels:
      app: checkoutservice
  template:
    metadata:
      labels:
        app: checkoutservice
    spec:
      serviceAccountName: online-boutique
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: server
          image: us-central1-docker.pkg.dev/google-samples/microservices-demo/checkoutservice:v0.10.3
          ports:
            - name: grpc
              containerPort: 5050
          env:
            - name: PORT
              value: "5050"
            - name: PRODUCT_CATALOG_SERVICE_ADDR
              value: "productcatalogservice:3550"
            - name: SHIPPING_SERVICE_ADDR
              value: "shippingservice:50051"
            - name: PAYMENT_SERVICE_ADDR
              value: "paymentservice:50051"
            - name: EMAIL_SERVICE_ADDR
              value: "emailservice:5000"
            - name: CURRENCY_SERVICE_ADDR
              value: "currencyservice:7000"
            - name: CART_SERVICE_ADDR
              value: "cartservice:7070"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          readinessProbe:
            tcpSocket:
              port: 5050
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          livenessProbe:
            tcpSocket:
              port: 5050
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 3
          resources:
            requests:
              cpu: 100m
              memory: 64Mi
            limits:
              cpu: 500m
              memory: 256Mi
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: checkoutservice
spec:
  selector:
    app: checkoutservice
  ports:
    - name: grpc
      port: 5050
      targetPort: 5050
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: currencyservice
  labels:
    app: currencyservice
spec:
  replicas: 2
  selector:
    matchLabels:
      app: currencyservice
  template:
    metadata:
      labels:
        app: currencyservice
    spec:
      serviceAccountName: online-boutique
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: server
          image: us-central1-docker.pkg.dev/google-samples/microservices-demo/currencyservice:v0.10.3
          ports:
            - name: grpc
              containerPort: 7000
          env:
            - name: PORT
              value: "7000"
            - name: DISABLE_PROFILER
              value: "1"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          readinessProbe:
            tcpSocket:
              port: 7000
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          livenessProbe:
            tcpSocket:
              port: 7000
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 3
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: currencyservice
spec:
  selector:
    app: currencyservice
  ports:
    - name: grpc
      port: 7000
      targetPort: 7000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: emailservice
  labels:
    app: emailservice
spec:
  replicas: 2
  selector:
    matchLabels:
      app: emailservice
  template:
    metadata:
      labels:
        app: emailservice
    spec:
      serviceAccountName: online-boutique
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: server
          image: us-central1-docker.pkg.dev/google-samples/microservices-demo/emailservice:v0.10.3
          ports:
            - name: grpc
              containerPort: 8080
          env:
            - name: PORT
              value: "8080"
            - name: ENABLE_PROFILER
              value: "0"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          startupProbe:
            tcpSocket:
              port: 8080
            periodSeconds: 10
            failureThreshold: 30
            timeoutSeconds: 5
          readinessProbe:
            tcpSocket:
              port: 8080
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          livenessProbe:
            tcpSocket:
              port: 8080
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 3
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: emailservice
spec:
  selector:
    app: emailservice
  ports:
    - name: grpc
      port: 5000
      targetPort: 8080
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  labels:
    app: frontend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      serviceAccountName: online-boutique
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: server
          image: us-central1-docker.pkg.dev/google-samples/microservices-demo/frontend:v0.10.3
          ports:
            - name: http
              containerPort: 8080
          env:
            - name: PORT
              value: "8080"
            - name: PRODUCT_CATALOG_SERVICE_ADDR
              value: "productcatalogservice:3550"
            - name: CURRENCY_SERVICE_ADDR
              value: "currencyservice:7000"
            - name: CART_SERVICE_ADDR
              value: "cartservice:7070"
            - name: RECOMMENDATION_SERVICE_ADDR
              value: "recommendationservice:8080"
            - name: SHIPPING_SERVICE_ADDR
              value: "shippingservice:50051"
            - name: CHECKOUT_SERVICE_ADDR
              value: "checkoutservice:5050"
            - name: AD_SERVICE_ADDR
              value: "adservice:9555"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          readinessProbe:
            tcpSocket:
              port: 8080
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          livenessProbe:
            tcpSocket:
              port: 8080
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 3
          resources:
            requests:
              cpu: 100m
              memory: 64Mi
            limits:
              cpu: 500m
              memory: 256Mi
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: frontend
spec:
  type: ClusterIP
  selector:
    app: frontend
  ports:
    - name: http
      port: 80
      targetPort: 8080
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: paymentservice
  labels:
    app: paymentservice
spec:
  replicas: 2
  selector:
    matchLabels:
      app: paymentservice
  template:
    metadata:
      labels:
        app: paymentservice
    spec:
      serviceAccountName: online-boutique
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: server
          image: us-central1-docker.pkg.dev/google-samples/microservices-demo/paymentservice:v0.10.3
          ports:
            - name: grpc
              containerPort: 50051
          env:
            - name: PORT
              value: "50051"
            - name: DISABLE_PROFILER
              value: "1"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          readinessProbe:
            tcpSocket:
              port: 50051
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          livenessProbe:
            tcpSocket:
              port: 50051
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 3
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: paymentservice
spec:
  selector:
    app: paymentservice
  ports:
    - name: grpc
      port: 50051
      targetPort: 50051
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: productcatalogservice
  labels:
    app: productcatalogservice
spec:
  replicas: 2
  selector:
    matchLabels:
      app: productcatalogservice
  template:
    metadata:
      labels:
        app: productcatalogservice
    spec:
      serviceAccountName: online-boutique
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: server
          image: us-central1-docker.pkg.dev/google-samples/microservices-demo/productcatalogservice:v0.10.3
          ports:
            - name: grpc
              containerPort: 3550
          env:
            - name: PORT
              value: "3550"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          readinessProbe:
            tcpSocket:
              port: 3550
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          livenessProbe:
            tcpSocket:
              port: 3550
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 3
          resources:
            requests:
              cpu: 100m
              memory: 64Mi
            limits:
              cpu: 500m
              memory: 256Mi
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: productcatalogservice
spec:
  selector:
    app: productcatalogservice
  ports:
    - name: grpc
      port: 3550
      targetPort: 3550
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: recommendationservice
  labels:
    app: recommendationservice
spec:
  replicas: 2
  selector:
    matchLabels:
      app: recommendationservice
  template:
    metadata:
      labels:
        app: recommendationservice
    spec:
      serviceAccountName: online-boutique
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: server
          image: us-central1-docker.pkg.dev/google-samples/microservices-demo/recommendationservice:v0.10.3
          ports:
            - name: grpc
              containerPort: 8080
          env:
            - name: PORT
              value: "8080"
            - name: PRODUCT_CATALOG_SERVICE_ADDR
              value: "productcatalogservice:3550"
            - name: DISABLE_PROFILER
              value: "1"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          startupProbe:
            tcpSocket:
              port: 8080
            periodSeconds: 10
            failureThreshold: 30
            timeoutSeconds: 5
          readinessProbe:
            tcpSocket:
              port: 8080
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          livenessProbe:
            tcpSocket:
              port: 8080
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 3
          resources:
            requests:
              cpu: 100m
              memory: 220Mi
            limits:
              cpu: 500m
              memory: 450Mi
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: recommendationservice
spec:
  selector:
    app: recommendationservice
  ports:
    - name: grpc
      port: 8080
      targetPort: 8080
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: shippingservice
  labels:
    app: shippingservice
spec:
  replicas: 2
  selector:
    matchLabels:
      app: shippingservice
  template:
    metadata:
      labels:
        app: shippingservice
    spec:
      serviceAccountName: online-boutique
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: server
          image: us-central1-docker.pkg.dev/google-samples/microservices-demo/shippingservice:v0.10.3
          ports:
            - name: grpc
              containerPort: 50051
          env:
            - name: APP_PORT
              value: "50051"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          readinessProbe:
            tcpSocket:
              port: 50051
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          livenessProbe:
            tcpSocket:
              port: 50051
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 3
          resources:
            requests:
              cpu: 100m
              memory: 64Mi
            limits:
              cpu: 500m
              memory: 256Mi
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: shippingservice
spec:
  selector:
    app: shippingservice
  ports:
    - name: grpc
      port: 50051
      targetPort: 50051
```
