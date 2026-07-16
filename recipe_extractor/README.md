# Recipe Extractor

**Ngôn ngữ:** Python
**Chức năng chính:** Hệ thống NLP (Xử lý Ngôn ngữ Tự nhiên) chuyên phân tích và bóc tách cấu trúc công thức nấu ăn bằng tiếng Việt.

Sử dụng mô hình CRF (Conditional Random Fields) chuyên cho bài toán NER (Named Entity Recognition), hệ thống này thực hiện:
- Nạp sẵn tệp trọng số huấn luyện cực nhẹ (`fss_ner_crf_optimized.joblib`) được tối ưu hóa đặc biệt cho thiết bị nhúng như Raspberry Pi.
- Khai thác danh mục đa dạng với hơn 250 công thức nấu ăn khác nhau.
- Tự động chuẩn hóa các đơn vị đo lường (grams, kg, ml) về một quy chuẩn thống nhất trước khi cung cấp đầu vào dạng JSON sạch sẽ cho **Recommend Daemon**.
