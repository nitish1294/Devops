FROM nginx:trixie-perl
WORKDIR app/repo
RUN apt update && apt upgrade -y && apt install -y nodejs npm
COPY . /app/repo
RUN cd /app/repo
RUN npm install
RUN npm run build
RUN mkdir -p /var/www/hrms
RUN cp -r dist/hrms/browser/* /var/www/hrms/
COPY nginx.conf /etc/nginx/conf.d/default.conf
