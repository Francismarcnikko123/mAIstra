import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'screens/capture_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Supabase.initialize(
    url: 'https://cvtshfshqccuncamvnkl.supabase.co',
    anonKey:
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN2dHNoZnNocWNjdW5jYW12bmtsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQxOTI0MzEsImV4cCI6MjA5OTc2ODQzMX0.MRfVoEoliVAXS6xa8wECGBjMVjq4VkIyfd39S3iGLMc',
  );

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'mAIstra',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.red),
        useMaterial3: true,
      ),
      home: const CaptureScreen(
        questionId: '3f4b3b6e-1234-4567-8910-abcdef123456',
      ),
    );
  }
}
