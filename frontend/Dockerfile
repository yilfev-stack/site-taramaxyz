FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package.json yarn.lock ./

# Install dependencies
RUN yarn install --frozen-lockfile

# Copy application code
COPY . .

# Build the app
RUN yarn build

# Install serve for production
RUN yarn global add serve

EXPOSE 3006

CMD ["serve", "-s", "build", "-l", "3006"]
