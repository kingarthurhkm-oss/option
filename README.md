# Dividend-Funded Protective Put Analyzer

NYSE/NASDAQ 상장 배당주에 대해 **배당금-풋옵션 스프레드 비율**을 계산하는 웹앱입니다.

## 전략 개요

**Dividend-Funded Protective Put** 전략은:
- 주식을 보유하면서 풋옵션을 매수해 하방 리스크를 방어
- 풋옵션 비용을 주식에서 나오는 배당금으로 충당
- 배당 커버리지(Spread Ratio)가 높을수록 순 방어 비용이 낮음

## 핵심 지표

| 지표 | 설명 |
|------|------|
| **배당 커버리지** | 기간 배당금 ÷ 풋 프리미엄 × 100. 100%이면 배당이 풋 비용 완전 충당 |
| **연환산 Spread Ratio** | 연간 배당 ÷ 연환산 풋 프리미엄. 만기를 1년으로 표준화한 비교 지표 |
| **순비용** | 풋 프리미엄에서 기간 배당금을 차감한 실질 방어 비용 |

## 실행 방법

```bash
# 의존성 설치
pip install -r requirements.txt

# 서버 실행
python app.py

# 브라우저에서 접속
open http://localhost:5000
```

## 데이터 소스

- **라이브 모드**: Yahoo Finance (yfinance) — 실시간 주가, 배당, 옵션 체인
- **데모 모드**: Black-Scholes 모델 기반 추정 데이터 (외부 API 차단 환경에서 자동 폴백)

## 지원 거래소

- NYSE (뉴욕증권거래소)
- NASDAQ

풋옵션이 상장된 종목만 분석 가능합니다.
