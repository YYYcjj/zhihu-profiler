"""Tests for Zhihu Profiler."""


def test_import():
    """Test that the package can be imported."""
    from zhihu_profiler import __version__
    assert __version__ == "0.1.0"


def test_models():
    """Test data models."""
    from zhihu_profiler.scraper.models import ZhihuUser, ZhihuAnswer, ScrapedData

    user = ZhihuUser(id="test", name="Test User")
    assert user.profile_url == "https://www.zhihu.com/people/test"

    answer = ZhihuAnswer(
        id=1,
        question_id=100,
        question_title="Test Question",
        content="Hello world",
    )
    assert answer.text_length == 11

    data = ScrapedData(user=user, answers=[answer])
    assert data.total_text_chars == 11


def test_preprocessor():
    """Test text preprocessing."""
    from zhihu_profiler.nlp.preprocessing import TextPreprocessor

    preprocessor = TextPreprocessor()
    text = "这是一个测试句子，包含一些常见词汇和https://example.com链接。"
    cleaned = preprocessor.clean_text(text)
    assert "https" not in cleaned
    assert "测试" in cleaned

    words = preprocessor.process(text)
    assert "测试" in words
    assert "句子" in words


def test_sentiment():
    """Test sentiment analysis."""
    from zhihu_profiler.nlp.sentiment import SentimentAnalyzer

    analyzer = SentimentAnalyzer()

    # Positive text
    result = analyzer.analyze_single("今天天气真好，心情非常愉快，一切都那么美好！")
    assert result.score > 0.4

    # Negative text
    result = analyzer.analyze_single("太糟糕了，什么都不顺利，心情很差。")
    assert result.score < 0.7


def test_personality():
    """Test personality analysis."""
    from zhihu_profiler.analysis.personality import PersonalityAnalyzer

    analyzer = PersonalityAnalyzer()
    profile = analyzer.analyze("创新和探索是非常重要的，我们需要不断尝试新的方法。")

    assert profile.big_five.openness > 40
    assert profile.cognitive_style != ""
    assert profile.social_orientation != ""
    assert profile.risk_tolerance != ""


def test_interests():
    """Test interest analysis."""
    from zhihu_profiler.analysis.interests import InterestAnalyzer

    analyzer = InterestAnalyzer()
    text = "人工智能和机器学习正在改变世界，Python是深度学习的主要语言。"
    profile = analyzer.analyze_from_text(text)

    assert len(profile.top_domains) > 0


def test_values():
    """Test value analysis."""
    from zhihu_profiler.analysis.values import ValueAnalyzer

    analyzer = ValueAnalyzer()
    text = "我一直在追求个人成长，不断突破自我，实现自己的人生目标。"
    profile = analyzer.analyze(text)

    assert "自我超越" in profile.value_scores


def test_style():
    """Test style analysis."""
    from zhihu_profiler.analysis.style import StyleAnalyzer

    analyzer = StyleAnalyzer()
    texts = [
        "这是一个测试句子。它是第二个句子。第三个句子也在这里。",
        "另一个段落的内容。包含了多个句子结构。用于测试写作风格分析。",
    ]
    profile = analyzer.analyze(texts)

    assert profile.avg_sentence_length > 0
    assert profile.vocabulary_richness > 0
