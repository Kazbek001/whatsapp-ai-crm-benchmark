package benchmark;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Locale;

public class Main {

    public static void main(String[] args) throws IOException {
        Path input = Path.of("data/sample/questions.csv");
        Path output = Path.of("results/benchmark_results.csv");

        if (!Files.exists(input)) {
            System.out.println("Test dataset not found: " + input);
            System.out.println("Please add the sample CSV file.");
            return;
        }

        List<String> lines = Files.readAllLines(
                input, StandardCharsets.UTF_8);

        Files.createDirectories(output.getParent());

        StringBuilder report = new StringBuilder();
        report.append("id,question,answer,correct,latency_ms\n");

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
            String answer = ruleBasedResponse(question);
            long latency = (System.nanoTime() - start) / 1_000_000;

            boolean isCorrect = answer.toLowerCase(Locale.ROOT)
                    .contains(expected);

            total++;
            totalLatency += latency;

            if (isCorrect) {
                correct++;
            }

            report.append(id).append(",")
                    .append(csvEscape(question)).append(",")
                    .append(csvEscape(answer)).append(",")
                    .append(isCorrect).append(",")
                    .append(latency).append("\n");
        }

        Files.writeString(output, report.toString(),
                StandardCharsets.UTF_8);

        double accuracy = total == 0
                ? 0.0 : (double) correct / total * 100;

        double averageLatency = total == 0
                ? 0.0 : (double) totalLatency / total;

        System.out.println("=== Benchmark Results ===");
        System.out.println("Chatbot: Rule-based baseline");
        System.out.println("Total questions: " + total);
        System.out.printf("Correct responses: %.2f%%%n", accuracy);
        System.out.printf("Average latency: %.3f ms%n", averageLatency);
        System.out.println("Report saved to: " + output);
    }

    private static String ruleBasedResponse(String question) {
        String text = question.toLowerCase(Locale.ROOT);

        if (text.contains("price") || text.contains("cost")) {
            return "Our pricing depends on the selected service.";
        }

        if (text.contains("hour") || text.contains("open")) {
            return "Our business hours are available in our company information.";
        }

        if (text.contains("sales") || text.contains("manager")
                || text.contains("contact")) {
            return "Please contact our sales manager for more information.";
        }

        if (text.contains("information") || text.contains("more")) {
            return "You can request more information from customer service.";
        }

        if (text.contains("service") || text.contains("help")
                || text.contains("hello")) {
            return "Hello! I can help you with our services.";
        }

        return "Thank you for your message. Please provide more details.";
    }

    private static String csvEscape(String value) {
        return "\"" + value.replace("\"", "\"\"") + "\"";
    }
}
