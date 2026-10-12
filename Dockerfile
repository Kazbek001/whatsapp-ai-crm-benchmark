
FROM maven:3.9.9-eclipse-temurin-17

WORKDIR /app

COPY pom.xml .
COPY src ./src
COPY data ./data
COPY config.yaml ./config.yaml

RUN mvn -q -DskipTests compile

CMD ["mvn", "-q", "exec:java"]

