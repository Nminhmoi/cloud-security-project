terraform {
  # Cung cấp bucket, key và region khi khởi tạo để hạ tầng lưu trạng thái có thể
  # được tạo riêng và không đưa giá trị riêng của tài khoản vào kho mã nguồn.
  backend "s3" {
    encrypt      = true
    use_lockfile = true
  }
}
