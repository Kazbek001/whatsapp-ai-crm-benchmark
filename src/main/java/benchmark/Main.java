
package benchmark;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public class Main {

    public static void main(String[] args) throws IOException {
        Map<String, String> config = loadConfig(Path.of("config.yaml"));

        Path input = Path.of(config.getOrDefault(
                "dataset_path", "data/sample/questions.csv"));
        Path output = Path.of(config.getOrDefault(
                "output_path", "results/benchmark_results.csv"));

        if (!Files.exists(input)) {
            System.out.println("Dataset not found: " + input);
            return;
        }

        List<String> lines = Files.readAllLines(
                input, StandardCharsets.UTF_8);

        StringBuilder report = new StringBuilder();
        report.append(
                "id,question,expected_intent,predicted_intent,answer,correct,latency_ms\n");

        int total = 0;
        int correct = 0;
        long totalLatency = 0;

        for (int i = 1; i < lines.size(); i++) {
            String[] row = lines.get(i).split(",", 3);

            if (row.length != 3) {
                continue;
            }

            String id = row[0].trim();
            String question = row[1].trim();
            String expected = row[2].trim().toLowerCase(Locale.ROOT);

            long start = System.nanoTime();
            String predicted = classifyIntent(question);
            String answer = generateRuleBasedAnswer(predicted);
            long latency = (System.nanoTime() - start) / 1_000_000;

            boolean isCorrect = expected.equals(predicted);

            total++;
            totalLatency += latency;

            if (isCorrect) {
                correct++;
            }

            report.append(id).append(",")
                    .append(csvEscape(question)).append(",")
                    .append(expected).append(",")
                    .append(predicted).append(",")
                    .append(csvEscape(answer)).append(",")
                    .append(isCorrect).append(",")
                    .append(latency).append("\n");
        }

        Files.createDirectories(output.getParent());
        Files.writeString(output, report.toString(),
                StandardCharsets.UTF_8);

        double accuracy = total == 0
                ? 0 : (double) correct / total * 100;

        double averageLatency = total == 0
                ? 0 : (double) totalLatency / total;

        System.out.println("=== Benchmark Results ===");
        System.out.println("System: Rule-based baseline");
        System.out.println("Total questions: " + total);
        System.out.printf("Intent accuracy: %.2f%%%n", accuracy);
        System.out.printf("Average latency: %.3f ms%n", averageLatency);
        System.out.println("Report: " + output);
    }

    private static String classifyIntent(String question) {
        String text = question.toLowerCase(Locale.ROOT);

        if (containsAny(text, "price", "cost", "pricing")) {
            return "pricing";
        }

        if (containsAny(text, "hour", "open", "opening")) {
            return "business_hours";
        }

        if (containsAny(text, "sales", "manager", "contact")) {
            return "sales";
        }

        if (containsAny(text, "information", "details")) {
            return "information";
        }

        if (containsAny(text, "help", "hello", "support", "service")) {
            return "support";
        }

        return "fallback";
    }

    private static String generateRuleBasedAnswer(String intent) {
        switch (intent) {
            case "pricing":
                return "Our pricing depends on the selected service.";
            case "business_hours":
                return "Our business hours are available in our company information.";
            case "sales":
                return "Please contact our sales manager for more information.";
            case "information":
                return "You can request more information from customer service.";
            case "support":
                return "Hello! I can help you with our services.";
            default:
                return "Thank you for your message. Please provide more details.";
        }
    }

    private static boolean containsAny(String text, String... words) {
        for (String word : words) {
            if (text.contains(word)) {
                return true;
            }
        }
        return false;
    }

    private static Map<String, String> loadConfig(Path path)
            throws IOException {
        Map<String, String> config = new HashMap<>();

        if (!Files.exists(path)) {
            return config;
        }

        for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
            String trimmed = line.trim();

            if (trimmed.isEmpty() || trimmed.startsWith("#")) {
                continue;
            }

            int separator = trimmed.indexOf(':');

            if (separator < 1) {
                continue;
            }

            String key = trimmed.substring(0, separator).trim();
            String value = trimmed.substring(separator + 1).trim();
            value = value.replaceAll("^['\"]|['\"]$", "");

            config.put(key, value);
        }

        return config;
    }

    private static String csvEscape(String value) {
        return "\"" + value.replace("\"", "\"\"") + "\"";
    }
}
