// Traditional Japanese Website JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling for navigation links
    const navLinks = document.querySelectorAll('a[href^="#"]');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Add fade-in animation on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    
    // Observe sections for animation
    const sections = document.querySelectorAll('.jp-welcome, .jp-screenshot, .jp-features, .jp-specs, .jp-download, .jp-links');
    sections.forEach(section => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(20px)';
        section.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(section);
    });
    
    // Add hover effect to feature cards
    const featureCards = document.querySelectorAll('.feature-card');
    featureCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.borderColor = '#f8b500';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.borderColor = '#8b4513';
        });
    });
    
    // Add click effect to buttons
    const buttons = document.querySelectorAll('.btn-jp');
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            // Don't prevent default - let links work
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = '';
            }, 100);
        });
    });
    
    // Simple visitor counter simulation (for aesthetic purposes only)
    const counterElement = document.querySelector('.counter-text');
    if (counterElement) {
        const randomVisits = Math.floor(Math.random() * 10000) + 5000;
        counterElement.textContent = `訪問者カウンター: ${randomVisits.toLocaleString('ja-JP')}`;
    }
    
    // Add current date to footer if needed
    const updateInfo = document.querySelector('.update-info');
    if (updateInfo) {
        const today = new Date();
        const year = today.getFullYear();
        const month = today.getMonth() + 1;
        const day = today.getDate();
        // Update date is already set in HTML, but you can dynamically update it here if needed
    }
    
    // Log for developers
    console.log('%c AutoFire Website ', 'background: #c41e3a; color: #ffffeb; font-size: 20px; padding: 10px;');
    console.log('%c 教育目的専用 - For Educational Purposes Only ', 'background: #f8b500; color: #1a1a1a; font-size: 14px; padding: 5px;');
});

// Add scroll-to-top functionality (traditional Japanese style)
window.addEventListener('scroll', function() {
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    
    // You can add a scroll-to-top button here if desired
    // For now, we keep it minimal like traditional Japanese sites
});

// Prevent right-click context menu on images (optional, common in Japanese sites)
const images = document.querySelectorAll('img');
images.forEach(img => {
    img.addEventListener('contextmenu', function(e) {
        // Allow right-click for now, but you can uncomment below to prevent
        // e.preventDefault();
        // alert('画像の保存は禁止されています');
    });
});
